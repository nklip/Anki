# Apache Kafka

<sub>[Back to Distributed Systems](../Readme.md#content)</sub>

**Apache Kafka is a distributed event streaming platform: applications append records to partitioned logs, and other applications read those records at their own pace.** Kafka retains the records according to a storage policy; reading a record does not remove it. This lets several services react to the same event and lets consumers replay retained history.

Start with the log and its readers, then explore storage guarantees, choose a deployment, and apply the patterns to an order system. Delivery guarantees, offset commits, and Kafka transactions have their own article: [Apache Kafka. Delivery and transactions](../Apache%20Kafka.%20Delivery%20and%20transactions/Readme.md).

1. [Models and internals](#1-models-and-internals)
2. [Storage and durability](#2-storage-and-durability)
3. [Deployment topologies](#3-deployment-topologies)
4. [Placement: Kafka, Redis, databases](#4-placement-kafka-redis-databases)
5. [Patterns](#5-patterns)
6. [Check your understanding](#6-check-your-understanding)

The article uses Apache Kafka 4.3 documentation and the standard `KafkaConsumer` subscription model. Its partition-assignment rules apply to consumer groups using either the classic or newer consumer protocol. **Share groups** use a different consumption model and are discussed separately. Topic names, event fields, and configuration examples are design choices, not universal defaults.

## 1. Models and internals

An online shop records that order `42` was created. Shipping, notifications, and analytics need that fact, but they do different work at different speeds. The shop publishes an event; each service consumes the event through its own group.

### Records, topics, partitions, and offsets

| Term | Meaning | Order-system example |
|---|---|---|
| Record / message | One stored item; an event usually describes something that happened | `OrderCreated` |
| Producer | Application that writes records | Order service |
| Consumer | Application that reads records | Shipping worker |
| Topic | Named collection of related records | `orders` |
| Partition | One ordered, append-only log within a topic | `orders`, partition `0` |
| Offset | Record position within one partition | Offset `42` in partition `0` |
| Broker | Kafka server that stores partition replicas and serves clients | Broker A |
| Consumer group | Consumers sharing partition assignments and saved progress | `shipping` |

A record can contain a **key**, a **value**, a timestamp, and headers. The key can identify the entity whose events belong together. The value carries the payload; headers carry additional metadata. Applications serialize keys and values into bytes and deserialize them when reading.

For example, publish with Kafka key `order-42` and this value in **JavaScript Object Notation (JSON)**:

```json
{
  "eventId": "evt-901",
  "eventType": "OrderCreated",
  "orderId": "order-42",
  "orderVersion": 1,
  "totalCents": 2599
}
```

`eventId` identifies this business event; `orderVersion` expresses application ordering. Neither is a Kafka offset. The broker assigns the offset when appending the record. `(topic, partition, offset)` identifies its log position; offset `42` in another partition is unrelated. Offsets can have gaps and are not timestamps or globally unique event IDs.

### The partition is the ordering boundary

Read each partition from left to right. The diagram shows logical logs; their replicas are introduced under durability.

![kafka-partition-log.svg](images/kafka-partition-log.svg)

With ordinary key-based partitioning, the same serialized key maps to the same partition while the partition count and routing rule remain unchanged. Different keys can share a partition. A producer can also select a partition explicitly, and custom partitioners can change the rule.

Kafka preserves the log order **within a partition**. It provides no total order across the topic's partitions. Choosing `orderId` as the key keeps one order's history together; it does not order all orders against one another. Concurrent producers must still agree on meaningful business sequencing, and consumers must preserve any ordering their side effects require.

Adding partitions can change a key's destination for future records; existing records stay where they were. Plan such changes when per-key order matters. A **hot key**, responsible for disproportionate traffic, can overload one partition even when other partitions are quiet.

### Inside the write and read path

A client uses `bootstrap.servers` to discover brokers and partition leaders. A **leader** is the replica accepting a partition's writes; **followers** copy its log. Producers send records to the relevant leaders. Consumers normally fetch from leaders; configured follower fetching is also possible.

A topic with **one partition** supplies one total append order. This can serve as a sequencer when its latency and capacity fit the application. The tradeoff is one leader's write path and at most one assigned consumer per standard group for that topic. It orders accepted appends, not real-world event times or concurrent requests according to an application fairness rule.

The producer batches records, and the broker appends them to log segment files. A **segment** is one file-sized portion of a partition log. The operating system's **page cache** keeps recently used file data in memory. Sequential access, batching, and optional compression reduce work per record and support high throughput.

Consumption is **pull-based**: producers push records to Kafka, but consumers request batches from their current positions at their own pace. A fetch can wait for data, a form of **long polling**, instead of repeatedly returning empty responses. A slow reader accumulates a backlog while other groups can continue. The available storage and retention window bound how long it can fall behind.

High throughput does not promise a fixed latency. Batch waiting, network traffic, replication, storage, and application processing all contribute. In the Java producer, `send()` is asynchronous: returning a future is different from receiving a successful broker acknowledgment. Observe the future or callback to detect delivery errors.

### Sharing work versus independent subscriptions

Follow one partition into each group. A group divides work internally; a different group gets an independent reading of the retained log.

![kafka-consumer-groups.svg](images/kafka-consumer-groups.svg)

Consumers using the same `group.id` and group-managed subscription share assignments. Each partition has at most one assigned consumer in that group at a time. One consumer may own several partitions. With three subscribed partitions, a fourth consumer cannot add another active partition reader to that group.

Use different group IDs for shipping and analytics when both need every event. Giving every shipping worker its own group ID would make them independent subscribers, potentially repeating the shipping work.

A **rebalance** changes assignments when membership or subscribed partitions change. The consumer protocol can move assignments incrementally; the disruption depends on the protocol and assignment strategy. Losing an assignment does not undo a database write a worker already made.

A **group coordinator** is the broker handling a group's membership and offset commits. Consumers send it periodic **heartbeats**, messages indicating that they are still reachable. If heartbeats stop for the session timeout, the coordinator removes the member and its partitions can be reassigned. With the classic protocol, the client configures `heartbeat.interval.ms` and `session.timeout.ms`; with the consumer protocol, the broker controls `group.consumer.heartbeat.interval.ms` and `group.consumer.session.timeout.ms`. Heartbeats establish reachability, not successful business processing; the [poll-timeout explanation](../Apache%20Kafka.%20Delivery%20and%20transactions/Readme.md#poll-timeout) adds the polling-progress check.

**Share groups are a separate option.** They allow multiple consumers to share a partition's records and acknowledge records individually. Their concurrency is not capped by partition count in the same way. Do not transfer the standard group's ownership and ordering assumptions to a share consumer.

## 2. Storage and durability

Retention asks which records should remain. Replication asks where copies exist. Acknowledgments ask what the producer has learned about a write. Keep these policies separate. The log start offset and high watermark bound consumer reads; the low watermark tracks deletion progress across live replicas.

### Retention and compaction

The top comparison removes old history; the bottom removes superseded values for the same key. Neither policy waits for every consumer to finish.

![kafka-retention-compaction.svg](images/kafka-retention-compaction.svg)

| Topic policy | What cleanup does | Useful for |
|---|---|---|
| `cleanup.policy=delete` | Removes eligible old segments using time or size limits | A bounded history of independent events |
| `cleanup.policy=compact` | Eventually removes older values for a key while retaining its latest state | Rebuilding a keyed state view |
| `cleanup.policy=compact,delete` | Compacts retained segments and also expires old segments | Keyed state with a bounded history window |

Time retention is not an exact per-record expiry timer: cleanup works on segments and runs asynchronously. A record can outlive the configured interval. Conversely, a size limit can remove history sooner than a time-only plan expects. `retention.bytes` is a per-partition limit.

Compaction preserves the offsets and order of surviving records. It does not immediately turn a topic into one row per key, and it does not add an arbitrary key-lookup API. A **tombstone**, a record with a key and a null value, marks deletion; the marker can itself be cleaned later. Recovery consumers must account for tombstone retention so deleted state is not resurrected.

Keep full event history when intermediate changes matter. A compacted latest balance cannot explain every deposit and withdrawal. With combined compaction and deletion, even a key's latest value can eventually expire.

### Replication, acknowledgments, and the ISR

A partition's **replication factor** counts all copies, including its leader. The **in-sync replica set (ISR)** contains replicas sufficiently caught up under Kafka's synchronization rules, including the leader. A configured copy can exist while being outside the ISR.

This example uses three copies and `min.insync.replicas=2`. Read the lower rows as different health states of that same partition.

![kafka-replication.svg](images/kafka-replication.svg)

| Producer setting | Successful acknowledgment means | Main limit |
|---|---|---|
| `acks=0` | The producer did not wait for broker confirmation | Broker receipt is unconfirmed |
| `acks=1` | The leader appended the record | Failure before replication can lose it |
| `acks=all` | The current ISR acknowledged the record | Requires suitable minimum ISR and surviving copies |

`acks=all` waits for the full current ISR, not every configured replica and not merely the minimum count. With three in-sync copies, it waits for three; with two, for two. If the ISR falls below the configured minimum, these writes fail. That deliberately trades write availability for stronger replication requirements.

For a cluster with at least three available brokers, this command creates the example topic. Run it from an extracted Kafka distribution, with a broker reachable at `localhost:9092`; the topic must not already exist:

```bash
bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic orders --partitions 3 --replication-factor 3 \
  --config min.insync.replicas=2
```

This creates three distinct logs with three copies each: nine partition replicas in total. The producer's `acks=all` setting is configured separately. The command illustrates topic configuration; it does not provision the brokers or controllers.

Replication acknowledgment is not a per-record `fsync` guarantee. **`fsync`** asks the operating system to synchronize file data to persistent storage. Kafka normally uses buffered file writes and replication; correlated failures of all copies still matter. A timeout can also leave the producer uncertain whether an append succeeded.

### Log start offset and low watermark: deletion progress

The **log start offset** is the lower boundary of a partition's available history. Consumers can obtain it with `beginningOffsets()`. Retention or explicit deletion can advance this boundary: if it becomes `13`, records below offset `13` are no longer available for replay. Advancing a consumer group's committed offset only saves that group's restart position; it does not move this storage boundary.

If a consumer tries to fetch below the log start offset, its position is out of range. The [`auto.offset.reset` policy](../Apache%20Kafka.%20Delivery%20and%20transactions/Readme.md#failure-scenarios) decides what follows: `earliest` resumes at the log start offset, `latest` skips to the end, and `none` makes `poll()` throw `OffsetOutOfRangeException`. Automatic resetting cannot recover records that have already been deleted.

Kafka's **low watermark** tracks deletion progress across a partition's live replicas. It is the minimum log start offset tracked across those replicas, including the leader. Here, **live** means the replica's broker is considered alive by Kafka's cluster metadata: an offline broker does not hold deletion back, but an alive follower that has fallen behind still can. The leader uses the low watermark to decide when an administrative `deleteRecords` request has completed, and the API returns it through `DeletedRecords.lowWatermark()`. A live follower still counts here even if it is outside the ISR; `acks=all` waits on the current ISR.

The deletion cutoff is exclusive: in the example below, requesting deletion before offset `13` removes records `10–12` and keeps `13–15`. Use one partition with the same three-copy replication factor as above: its leader and two live followers initially start at `10`. In the middle state, the leader and replica-2 have advanced their log starts to `13`, but replica-3 still starts at `10`. The low watermark remains `min(13, 13, 10) = 10`, so deletion is incomplete even though the leader has already removed `10–12`. Once replica-3 advances to `13` and the leader learns its progress, the low watermark reaches `13` and the request completes. This tracks logical unavailability; reclaiming the underlying segment files can happen later.

**Consumption and deletion are independent.** The diagram does not say whether records `13–15` have been consumed; they remain because this request only removes offsets below `13`. Records `10–12` can be deleted even if a consumer group has never read or processed them. Neither time/size retention nor `deleteRecords` waits for consumer groups to consume records or commit offsets, and consuming or committing a record does not delete it. The low watermark confirms deletion progress across broker replicas; it does not confirm that consumers finished processing the deleted records. A consumer that still needs those offsets faces the out-of-range behavior described above.

Read the three states from top to bottom: before deletion, deletion in progress, and deletion complete. Each numbered cell is a record offset, the leader is on the left, and its two followers are on the right. Followers learn the leader's log start offset through fetch responses. Dashed slots labeled **gone** mark history unavailable on that replica; **pending** records on replica-3 explain why the low watermark can lag behind the leader's log start. Retained offsets keep their original numbers.

![kafka-low-watermark-deletion.svg](images/kafka-low-watermark-deletion.svg)

### High watermark: replication and consumer visibility

The **high watermark (HW)** is the exclusive upper offset boundary of the history Kafka considers committed by replication. Brokers use it to limit consumer reads: a record's offset must be strictly below this boundary. This keeps consumers from seeing a write before replication has committed it.

Continue the deletion example with log start offset `13` and retained records `13–15`. The leader now appends new records `16–18`. A replica's **log end offset** is the next append position: a replica holding records through `18` has log end `19`. This example keeps all three replicas in the ISR, satisfies `min.insync.replicas=2`, and has no transactions or further deletion. Briefly lagging behind the leader does not automatically remove a follower from the ISR.

**Before the followers catch up**, the leader's log end is `19`, but each follower's is still `16`. The high watermark remains `16`, so consumers can read `13–15`; the new records `16–18` are held back, even if their producer received `acks=1`. **After the followers catch up**, they request their next records from offset `19`, telling the leader that they have copied through `18`. Once the leader has learned this progress from every follower in the ISR, the high watermark advances to `19`, and records `13–18` are readable. Offset `19` itself remains outside that exclusive boundary.

Read the two states from top to bottom. The leader is on the left, and its two followers are on the right. Dashed slots labeled **absent** have not yet been copied to a follower; **held** records exist on the leader but are not yet readable by consumers. The vertical line on the leader marks the high watermark moving from `16` to `19`. **Visible** means available to consumers, whether or not any consumer has read the record. Consumer reads and committed offsets do not advance the high watermark; replication does. The log start offset stays at `13` throughout.

![kafka-high-watermark-replication.svg](images/kafka-high-watermark-replication.svg)

This boundary applies even to `read_uncommitted`. Under that isolation level, `endOffsets()` returns the high watermark. With `read_committed`, it returns the [last stable offset (LSO)](../Apache%20Kafka.%20Delivery%20and%20transactions/Readme.md#transaction-aware-consumers), which can stop earlier while transactions remain open; these consumers also filter out aborted records. The high watermark is shared partition state. A group's committed offset is its own restart progress, so these are two different meanings of “committed.”

Together, the log start offset and high watermark bound ordinary consumer reads. In the final state above, log start `13` and high watermark `19` make records `13–18` readable. Records below `13` are unavailable; a later record at offset `19` must cross the replication boundary before consumers can read it. The deletion API's low watermark tracks the lower boundary across live replicas: the middle deletion state shows it still at `10` while the leader's log start is already `13`.

The comparison diagram in [§5](#pattern-4-aggregate-streams-into-a-queryable-result) puts these broker offset boundaries beside event-time watermarks.

When a leader fails, Kafka elects a suitable replacement and clients refresh their routing. Modern Kafka can track **eligible leader replicas (ELR)** outside the current ISR that are still safe election candidates. With ELR enabled, the strict minimum-ISR rule prevents the high watermark from advancing while the ISR is smaller than `min.insync.replicas`; this helps make those tracked replicas safe candidates. An unsafe, or **unclean**, election can instead lose acknowledged history. Keeping unsafe election disabled may leave a partition unavailable until a suitable copy returns.

### Capacity and operational checks

For an illustrative uncompressed input of `10 MB/s`, one day contains about `864 GB` of payload. Three full copies need about `2.6 TB` before indexes, operational headroom, and other overhead. Compression and storage policies change the estimate; measure representative data. Replication also consumes network and disk bandwidth.

**Partitions have a resource cost even when traffic is low.** Each replica brings log segments and indexes, file descriptors, memory mappings, and metadata; active readers and writers also consume memory. More partitions increase the work involved in assignments, leader elections, and recovery. Choose a partition count from measured throughput, required consumer parallelism, and tested broker and recovery capacity. For metrics, many metric-name keys can share a bounded set of partitions; automatically creating one partition for every new name makes resource use grow with the number of distinct names. Replication multiplies the number of replicas to budget for.

Monitor under-replicated partitions, partitions without leaders, minimum-ISR violations, disk space, request latency, producer errors, and controller health. Monitor **consumer lag**, the distance between a reader's progress and the log's end, alongside the age of unprocessed events. Offset distance alone is not a precise count of business events when offsets have gaps.

Retention must cover the intended outage and catch-up window. A consumer that processes more slowly than new events arrive cannot catch up without additional capacity or less work per event. Test recovery from both worker failure and lost storage; live copies alone do not preserve an independent historical backup.

### Archival and tiered storage

For an **independent archive**, export records to files in object storage such as Amazon S3, using an application consumer or an installed Kafka Connect sink connector, a component that exports Kafka data to another system (Pattern 3). Give the archive its own retention policy, preserve the event IDs, keys, schemas, and source positions needed for replay, and advance export progress only after durable storage succeeds. Rehearse restoring those files into a new topic or application state. Export retries and replay still need duplicate handling; creating files alone does not establish a recovery procedure.

**Tiered storage** moves older, closed log segments to remote storage while Kafka continues to serve retained records through its normal fetch interface. It reduces the history that must remain on broker disks: `local.retention.ms` and `local.retention.bytes` govern the local tier, while `retention.ms` and `retention.bytes` govern the overall retained history. Remote segments still participate in Kafka's retention lifecycle, so that tier is not an independent historical backup.

Kafka 4.3 requires a configured **RemoteStorageManager** implementation, the plugin that handles remote log storage; the distribution does not include one. Its documented tiered-storage limitations also exclude compacted topics. Choose between longer Kafka history and an independent archive according to the required replay interface, retention ownership, and restore process.

## 3. Deployment topologies

Kafka separates **data storage** on brokers from **cluster metadata management** on controllers. Metadata describes objects such as topics, replica placement, and leaders. **KRaft** uses the Raft consensus protocol to keep controllers in agreement about metadata; Kafka 4.x does not require ZooKeeper.

### A local development server

One process can combine broker and controller roles with `process.roles=broker,controller`. It is useful for learning. With replication factor one, its partitions have no alternate copy; stopping the machine stops that setup. Several partitions on one broker add logical logs, not independent machines.

### Separate brokers and controllers

The upper row manages metadata. The lower row stores application records. Solid arrows show application data; dashed arrows show metadata coordination.

![kafka-kraft-topology.svg](images/kafka-kraft-topology.svg)

A production deployment commonly uses separate broker and controller processes. A **quorum** is the required set of participants for agreement. Three voting controllers need a majority of two to maintain the metadata quorum; five need three. Controller counts and partition replication factors are independent decisions: three controllers do not create three copies of every order event.

Distribute brokers and replicas across suitable failure locations. Different brokers lead different partitions and follow others, spreading load. More brokers provide useful capacity when partitions and their leadership are placed on them; adding a broker does not automatically split an existing partition or eliminate a hot key.

| Arrangement | What it adds | Main consideration |
|---|---|---|
| One combined node | Simple local setup | No independent failover capacity |
| Multiple brokers with a controller quorum | Partition capacity and replicated recovery | Broker health, quorum health, and replica placement all matter |
| Multiple clusters with mirroring | Regional or organizational separation | Replication lag and an application failover plan |

### Separate clusters and disaster recovery

**MirrorMaker 2** uses Kafka Connect to copy data between clusters. This is different from followers copying a leader inside one cluster. A source acknowledgment does not imply that the remote cluster already has the record.

Cross-cluster recovery needs decisions about missing recent events, client redirection, group-offset translation, and duplicate effects. Measure replication lag and rehearse the switch. Managed services can automate operations, but applications still need explicit ordering, retention, and retry contracts.

## 4. Placement: Kafka, Redis, databases

Choose what each layer owns. A **source of truth** is the authoritative state from which other views can be rebuilt. In this shop example, the order database owns accepted orders, Kafka carries their events, and downstream stores serve queries.

![kafka-data-placement.svg](images/kafka-data-placement.svg)

| Need | Appropriate role in this example |
|---|---|
| Accept an order and enforce business constraints | Database transaction in the order service |
| Retain changes for several independent readers | Kafka topic |
| Read an order by ID or search products | Query database or search index populated by a consumer |
| Cache a frequently read result or update a shared counter | Redis |
| Store a large report, image, or video | Object storage; send an object reference through Kafka |
| Deliver reusable web responses and files near users | Content delivery network (CDN) |

Kafka's durable log can instead be authoritative in a deliberately designed **event-sourced system**, where recorded events define state. Pattern 7 develops its history, concurrency, and recovery requirements. Enabling Kafka alone does not make a database-derived topic the owner of the database's facts.

A **materialized view** stores a derived result for convenient queries. Its consumer can lag, so accepting an order does not mean every search index and dashboard already includes it. Define what the user sees while those views catch up.

Kafka is useful when retained history, independent consumers, and streaming throughput justify operating it. A shared cache, a simple synchronous call, or a small job queue can be sufficient for narrower requirements. Choose the required behavior before the product.

## 5. Patterns

Each pattern identifies the user-visible behavior, the Kafka data, its placement, and the failure that needs an application decision.

**This is an evidence-informed teaching order, not a measured frequency ranking.** Apache Kafka's use-case page is editorial; the 2017 survey is nine years old at this article's 2026 review; question-tag counts can reflect both adoption and troubleshooting difficulty; and pattern literature is qualitative. None cleanly measures the frequency of these seven patterns. Confidence is strongest in placing independent reactions and buffering first and event sourcing last. Positions 3–6 are a judgment call: integration introduces the tooling, aggregation creates views, the outbox explains reliable publication, and replay repairs those views.

### Pattern 1. Let services react independently

The group diagram in [§1](#sharing-work-versus-independent-subscriptions) supplies this pattern: each service has its own progress through the same topic.

**User interaction.** After an order is accepted, a shipping service arranges fulfillment and an analytics service updates demand statistics. Analytics can pause without making shipping wait for it.

**Kafka data.** Both groups read `OrderCreated`; instances within `shipping` share shipping partitions. Choose topic contracts according to business meaning and access needs.

**Placement.** Each service writes its own database or derived view. A public API reads those stores to display status.

**Main trap.** Reading an event does not make several services one transaction. A later cancellation, a repeated event, and a consumer outage need explicit business handling. Partition order alone does not enforce workflow rules in an external system.

### Pattern 2. Buffer ingestion during surges and sink outages

The same separation between producer and consumer can deliberately hold work that a slower destination cannot process immediately. The diagram tracks unread records; reading them does not remove their retained Kafka copies.

![kafka-ingestion-buffer.svg](images/kafka-ingestion-buffer.svg)

**User interaction.** A monitoring agent submits measurements during a traffic surge. Here ingestion waits for a successful `acks=all` write with a suitable minimum ISR before acknowledging acceptance. A consumer writes those measurements to a time-series database, a store optimized for timestamped observations. The ingestion acknowledgment confirms Kafka's replication requirement was met; it does not mean the database already contains the measurements.

**Kafka data.** A retained `measurements` topic absorbs the temporary difference between arrival and processing rates. In an illustrative burst of 6,000 records per second with a sink processing 2,000, a 30-second burst adds 120,000 unread records. If arrivals then fall to 1,000 per second and processing stays at 2,000, the backlog drains at 1,000 per second and takes 120 seconds to clear. These rates assume comparable records and sustained processing capacity.

**Placement.** Kafka holds pending input independently of the sink; consumers pull batches at a rate the destination can sustain. This also permits ingestion during a bounded sink outage. Apply the same separation to email work or click aggregation when eventual processing is acceptable, with duplicate-safe effects and visible processing status where needed.

**Main trap.** A buffer buys time, not unlimited throughput or storage. Retention can expire unread records while the backlog is still draining. Budget for the burst or outage plus catch-up time and a margin, including size-based retention. Watch the oldest unread event's age alongside lag. If sustained arrivals equal or exceed processing capacity, recovery cannot clear the backlog without more sink capacity, less work, or throttled intake. Adding workers helps only when partition parallelism and the destination can support them.

### Pattern 3. Move data with Kafka Connect

Follow the arrows from the product database through the source connector, Kafka topic, and sink connector to the search store. The source brings changes into Kafka; the sink takes them out. Connector tasks run in Connect workers, separate from the brokers storing the topic.

![kafka-connect.svg](images/kafka-connect.svg)

**User interaction.** A merchant updates a product; a search view later reflects the change.

**Kafka data.** A **source connector** imports external data into Kafka. A **sink connector** exports Kafka data to another system. **Change data capture (CDC)** reads database changes for publication; a source connector such as Debezium can capture those changes. Kafka Connect runs the connector tasks in worker processes; distributed mode can rebalance tasks when workers change.

**Placement.** The product database remains authoritative; a connector supplies events and another connector or application updates the search store. Connector implementations are installed components with their own supported sources, formats, and guarantees.

**Main trap.** “Uses Connect” does not imply `exactly-once` delivery to every destination. Verify the connector's recovery behavior and the destination's write semantics. Also check the data contract: a **schema** defines fields and types, and replay may encounter older schemas long after the producer changes.

### Pattern 4. Aggregate streams into a queryable result

The application below keeps an evolving count and publishes its result. Its processing code runs outside the Kafka brokers.

![kafka-stream-processing.svg](images/kafka-stream-processing.svg)

**User interaction.** A merchant dashboard shows orders per minute. **Kafka Streams** is an application library for transformations, joins, and aggregations over Kafka records.

**Kafka data.** An application reads `orders`, groups events by the desired key and time window, and publishes counts to `order-counts`. A **window** groups events into a time interval. Event time means when the event happened; processing time means when the application handles it. An event can arrive after newer events, so closing an event-time window needs a deliberate late-arrival policy.

The word **watermark** has three distinct meanings in this article. The broker's **high watermark** from [§2](#high-watermark-replication-and-consumer-visibility) limits reads by replication progress. An **event-time watermark** in stream processing estimates progress through event timestamps; an event arriving behind that estimate is late, and the processing policy decides whether it can still update a result. The estimate does not prove that older events can never arrive.

The **low watermark** from [§2](#log-start-offset-and-low-watermark-deletion-progress) tracks deletion progress across live replicas.

Kafka Streams uses **stream time**, the maximum record timestamp observed so far by each task, and a window's **grace period** to decide when to reject late records. For a one-minute window covering `12:00:00 ≤ event time < 12:01:00`, a 30-second grace permits late updates until stream time moves past `12:01:30`. An arriving event timestamped `12:00:50` still belongs to that original window; grace extends acceptance time, not window membership. Stream time advances with records, not merely with the wall clock. Longer grace can accept more late events, but requires retaining window state longer and postpones when the result can be considered final; intermediate results may be emitted earlier.

Choose grace for each window in the Kafka Streams API, for example with `TimeWindows.ofSizeAndGrace(size, grace)`. There is no global Kafka broker `watermark` setting for this late-event policy.

The comparison diagram below brings the three watermark meanings together. Its top row compares broker deletion and replication progress. In the upper-right panel, **Readable** contains records `41` and `42`, while **Held back** contains `43` and `44`. The bottom panel shows event-time progress owned by the stream processor, including Kafka Streams' stream time and grace period. Compare its timestamp units with the broker offset boundaries above it.

![kafka-watermarks.svg](images/kafka-watermarks.svg)

**Placement.** Streams tasks keep local state; Kafka changelog topics support restoration. A downstream service can maintain a queryable dashboard view. Repartition topics may move records to place the same aggregation key together.

**Main trap.** Replaying a naive increment can count twice. For supported Kafka processing, configure `processing.guarantee=exactly_once_v2` to coordinate offsets, state changes, and Kafka outputs. This still does not include an arbitrary external API call or remove duplicate business events already present in the input.

### Pattern 5. Publish database changes with a transactional outbox

Pattern 3 showed how changes reach Kafka. [Transactional Outbox](../Patterns.%20Transactional%20Outbox/Readme.md) preserves the obligation to publish when a database commit and a Kafka send cannot happen atomically. The database boundary below contains both the business row and the pending event; publication follows that transaction's commit.

![kafka-outbox.svg](images/kafka-outbox.svg)

**User interaction.** A customer submits an order. The order service commits the order and an **outbox row**, a pending publication record, in the same database transaction. It can then report that the order was accepted without waiting for shipping to finish.

**Kafka data.** A relay publishes the outbox event `evt-901` to `orders`, keyed by `orderId`. The CDC tooling introduced in Pattern 3 can capture an outbox table and route its events; Debezium supports this approach. Keep that event ID stable across retries for deduplication and a per-order version when needed.

**Placement.** The database owns the order and pending publication. Kafka retains the published event; each downstream service owns its own resulting state. Monitor how long rows remain unpublished.

**Main trap.** Committing an order and directly sending to Kafka are two independent writes. A crash between them can omit the event. The outbox makes the publication obligation durable, but a relay retry can publish a duplicate. A consumer can atomically store `eventId` with its business effect in its own database so replay recognizes completed work.

### Pattern 6. Rebuild a view and handle failed records

**User interaction.** A corrected search index or dashboard should include previously published events. A new consumer group or controlled offset reset can reread the required retained data.

**Kafka data.** Use a full retained event log to reconstruct history, or a suitable compacted topic to reconstruct latest keyed state. The retention diagram in [§2](#retention-and-compaction) shows why these are different inputs.

**Placement.** Build into a separate destination, compare its results, then switch queries when it is ready. Replaying events that originally sent emails should rebuild state without unintentionally emailing users again.

**Main trap.** A **poison record**, one that repeatedly fails processing, needs a policy. Retrying in place preserves the sequence but can block that partition. A retry topic or **dead-letter topic**, which holds failed records for investigation, permits progress but can break the original processing order. These are application or connector policies, not an automatic standard-consumer feature. Keep the original event ID, error context, and an explicit recovery owner; verify that failed-record publication succeeded before advancing past it.

### Pattern 7. Reconstruct state from an authoritative event log

Here the accepted events define state. Follow one ordered stream through ordinary updates and then through snapshot recovery.

![kafka-event-sourcing.svg](images/kafka-event-sourcing.svg)

**User interaction.** An order system accepts a change and later shows the state derived from its accepted events. A **command** requests a change; an **event** records an accepted fact. Business validation turns a request such as `CreateOrder` into a fact such as `OrderCreated`. A command log alone does not record whether each request was accepted or rejected.

**Kafka data.** Preserve the accepted events needed to reconstruct state, with stable event IDs, entity keys, versions, and interpretable schemas. A **state machine** applies each event to the previous state using deterministic rules: the same starting state and ordered events produce the same result. For the running order example, the accepted creation fact remains `evt-901`.

**Placement.** A **snapshot** saves derived state together with the stream position through which it was computed. Restore a snapshot through position `100`, then apply events `101` onward from that same ordered stream. With multiple Kafka partitions, recovery must track the corresponding position in each partition; Kafka has no single topic-wide offset. **Command Query Responsibility Segregation (CQRS)** separates the model handling changes from models serving queries. It is often paired with event sourcing, but neither requires the other, and derived query views can lag.

**Main trap.** Kafka orders appends; it does not automatically enforce expected entity versions, validate business transitions, or provide an event store's per-entity query interface. The application must enforce ownership or concurrency rules around validation and append. Preserve the necessary history and schema interpretation, and verify that snapshots match their recorded positions. A snapshot accelerates recovery but cannot replace a complete event trail when an audit requires every change. Replaying state transitions must not resend emails or repeat payment calls; those effects require separate handling.

## 6. Check your understanding

Try answering each question before expanding its answer.

1. Keys A and B both map to partition P0. Is that valid, and what ordering does it give relative to P1? What would a one-partition topic change, and at what cost?

   <details>
   <summary>Answer</summary>

   Yes. Different keys can share P0 and its log order, but Kafka supplies no total order between P0 and P1. One partition supplies a total append order, with one leader's write path and at most one assigned consumer per standard group for that topic. It does not establish real-world time order.

   </details>

2. The `orders` topic has three partitions and four shipping consumers. Can all four receive partition assignments? How should analytics subscribe if it also needs every event?

   <details>
   <summary>Answer</summary>

   At most three can hold assignments to those partitions. Analytics needs a different group ID for independent consumption and progress.

   </details>

3. Replication factor is three, `min.insync.replicas=2`, and `acks=all`. How many copies must acknowledge with an ISR of three? Of two? What happens with one?

   <details>
   <summary>Answer</summary>

   All three, then both. With only one in-sync copy, the minimum is not met and these writes fail. The minimum does not reduce `all` to a fixed count of two.

   </details>

4. The leader has record `16`, but the high watermark is still `16`. Can `read_uncommitted` read it, or can the group's committed offset make it visible? How does this watermark differ from an event-time watermark? What does a Streams window's grace extend?

   <details>
   <summary>Answer</summary>

   No: reads must stay below the high watermark. Replication must advance it beyond `16`; a group's committed offset cannot make unreplicated data visible. This is an offset boundary, whereas an event-time watermark estimates timestamp progress. Streams grace extends acceptance of late updates to an existing window, not that window's event-time membership.

   </details>

5. Can consuming a record protect it from deletion? Does compaction preserve every event, and does it renumber surviving offsets?

   <details>
   <summary>Answer</summary>

   No. Cleanup is independent of consumption. Compaction can remove superseded events while retaining latest keyed state; surviving offsets keep their original numbers. A full-history rebuild needs the required history still retained.

   </details>

6. Does a quorum of three KRaft controllers create three copies of every order record?

   <details>
   <summary>Answer</summary>

   No. Controllers replicate metadata. Application-record copies depend on each topic's replication factor and broker placement.

   </details>

7. In the product-to-search example, what does each Connect connector do, and where do its tasks run?

   <details>
   <summary>Answer</summary>

   The source connector imports database changes into Kafka; the sink connector exports records to the search store. Their tasks run in Connect worker processes, outside the brokers.

   </details>

8. Does an outbox guarantee that `evt-901` is published only once? How can a consumer recognize completed work on replay?

   <details>
   <summary>Answer</summary>

   No. The outbox preserves a publication obligation, but relay retries can duplicate events. A consumer can atomically store the event ID with its business effect in its own database so replay recognizes completed work.

   </details>

9. A burst leaves 120,000 unread records. Arrivals then run at 1,000 records per second and the sink handles 2,000. How long does catch-up take? Can records expire before it finishes?

   <details>
   <summary>Answer</summary>

   The net drain rate is 1,000 records per second, so catch-up takes 120 seconds at those sustained rates. Yes: retention cleanup does not wait for the consumer. The available history must cover both the accumulated delay and catch-up; size limits can shorten it.

   </details>

10. How does an accepted-event log differ from a command log? What must accompany a snapshot, and which side effects should recovery avoid?

    <details>
    <summary>Answer</summary>

    Commands request changes; accepted events record the resulting facts. A snapshot needs the exact stream position or per-partition positions represented by its state, so replay starts immediately afterward. Recovery should rebuild state without repeating external payments, emails, or other original side effects.

    </details>

11. Why can one partition per metric name become expensive even when most names have low traffic?

    <details>
    <summary>Answer</summary>

    Every replica adds logs, indexes, metadata, and operating-system resources, and more partitions add coordination and recovery work. Many metric-name keys can share a bounded partition count sized for measured capacity and parallelism.

    </details>

12. Does moving old segments to Kafka's remote tier preserve an independent backup? How would you create an archive with separate retention?

    <details>
    <summary>Answer</summary>

    No. Kafka retention still governs remote segments. Export records and replay metadata to independently retained files, checkpoint durable exports, and test restoration; the archive's own storage policy must preserve the required history.

    </details>

13. The leader and one live follower start at `13`, but a second live follower still starts at `10`. What is the low watermark, and is a request to delete records below `13` complete? Would being outside the ISR exclude that second live follower from the calculation?

    <details>
    <summary>Answer</summary>

    The low watermark is `min(13, 13, 10) = 10`, so deletion below `13` is not complete. The leader uses it to track completion of administrative record deletion across live replicas. A live follower outside the ISR still counts; a follower on a broker no longer considered alive does not. This boundary is separate from a group's committed offset and the replication high watermark.

    </details>

# Sources

- [Apache Kafka introduction: events, topics, partitions, and retention independent of consumption](https://kafka.apache.org/43/getting-started/introduction/)
- [Apache Kafka use cases: editorial descriptions of messaging, buffering, processing, and event sourcing](https://kafka.apache.org/uses/)
- [Confluent's 2017 Kafka community survey: historical, overlapping pipeline, processing, and integration categories](https://www.confluent.io/blog/2017-apache-kafka-survey-streaming-data-on-the-rise/)
- [Stack Exchange tags API: tag popularity counts questions, not application deployments](https://api.stackexchange.com/docs/tags)
- [ProducerRecord API: record fields, partition selection, and timestamps](https://kafka.apache.org/43/javadoc/org/apache/kafka/clients/producer/ProducerRecord.html)
- [ConsumerRecord API: topic, partition, offset, key, and value](https://kafka.apache.org/43/javadoc/org/apache/kafka/clients/consumer/ConsumerRecord.html)
- [Kafka design: delivery guarantees, log storage, pull consumption, replication, transactions, share groups, and compaction](https://kafka.apache.org/43/design/design/)
- [KafkaProducer API: asynchronous sends, retry idempotence, and transactions](https://kafka.apache.org/43/javadoc/org/apache/kafka/clients/producer/KafkaProducer.html)
- [Kafka 4.3.0 partition log: last stable offset and read-committed visibility](https://github.com/apache/kafka/blob/4.3.0/storage/src/main/java/org/apache/kafka/storage/internals/log/UnifiedLog.java#L671-L685)
- [Producer configuration: acknowledgments, idempotence, transaction identity, and timeouts](https://kafka.apache.org/43/configuration/producer-configs/)
- [KafkaConsumer API: group assignments, committed offsets, out-of-range recovery, and beginning/end offsets](https://kafka.apache.org/43/javadoc/org/apache/kafka/clients/consumer/KafkaConsumer.html)
- [Kafka Admin API: deleting records below an exclusive partition offset](https://kafka.apache.org/43/javadoc/org/apache/kafka/clients/admin/Admin.html#deleteRecords(java.util.Map))
- [DeletedRecords API: the low watermark returned after deletion](https://kafka.apache.org/43/javadoc/org/apache/kafka/clients/admin/DeletedRecords.html)
- [KIP-107: log start offsets, deletion progress across live replicas, and deferred physical cleanup](https://cwiki.apache.org/confluence/spaces/KAFKA/pages/67636826/KIP-107+Add+deleteRecordsBefore+API+in+AdminClient)
- [Kafka 4.3.0 partition implementation: low watermark, live replicas, and completion of deletion requests](https://github.com/apache/kafka/blob/4.3.0/core/src/main/scala/kafka/cluster/Partition.scala#L1055-L1080)
- [Kafka distribution: group coordinators and compacted offset storage](https://kafka.apache.org/43/implementation/distribution/)
- [Consumer configuration: offset reset, automatic commits, polling, and isolation](https://kafka.apache.org/43/configuration/consumer-configs/)
- [KafkaShareConsumer API: shared partitions and individual record acknowledgment](https://kafka.apache.org/43/javadoc/org/apache/kafka/clients/consumer/KafkaShareConsumer.html)
- [Consumer rebalance protocol: incremental assignment and migration](https://kafka.apache.org/43/operations/consumer-rebalance-protocol/)
- [Topic configuration: cleanup, retention, minimum ISR, and file synchronization](https://kafka.apache.org/43/configuration/topic-configs/)
- [Eligible leader replicas: safe election candidates and strict minimum ISR](https://kafka.apache.org/43/operations/eligible-leader-replicas/)
- [Basic Kafka operations: partition expansion, placement, replication, and group progress](https://kafka.apache.org/43/operations/basic-kafka-operations/)
- [Hardware and operating systems: storage, cache, and partition resource costs](https://kafka.apache.org/43/operations/hardware-and-os/)
- [Monitoring: broker, controller, producer, consumer, and connector metrics](https://kafka.apache.org/43/operations/monitoring/)
- [Kafka tiered storage: remote segments, retention, required plugins, and limitations](https://kafka.apache.org/43/operations/tiered-storage/)
- [KRaft: broker/controller roles, quorum size, and deployment considerations](https://kafka.apache.org/43/operations/kraft/)
- [KRaft versus ZooKeeper: metadata management and separated process roles](https://kafka.apache.org/43/getting-started/zk2kraft/)
- [Broker configuration: replication controls, transaction-state durability, and maximum transaction timeout](https://kafka.apache.org/43/configuration/broker-configs/)
- [Cross-cluster mirroring: MirrorMaker 2, topology, lag, and consumer migration](https://kafka.apache.org/43/operations/geo-replication-cross-cluster-data-mirroring/)
- [Kafka Connect overview: reusable integration with external systems](https://kafka.apache.org/43/kafka-connect/overview/)
- [Kafka Connect user guide: workers, connectors, data formats, errors, and delivery guarantees](https://kafka.apache.org/43/kafka-connect/user-guide/)
- [AWS transactional outbox: database changes and reliable eventual publication](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
- [Debezium outbox event router: event identity, entity keys, and routing](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
- [Kafka Streams core concepts: windows, event time, and processing state](https://kafka.apache.org/43/streams/core-concepts/)
- [Apache Beam programming guide: event-time watermarks and late data](https://beam.apache.org/documentation/programming-guide/#watermarks-and-late-data)
- [Kafka Streams ProcessingContext: per-task stream time](https://kafka.apache.org/43/javadoc/org/apache/kafka/streams/processor/api/ProcessingContext.html#currentStreamTimeMs())
- [Kafka Streams TimeWindows: window boundaries and grace periods](https://kafka.apache.org/43/javadoc/org/apache/kafka/streams/kstream/TimeWindows.html)
- [Kafka Streams architecture: tasks, local state, and recovery](https://kafka.apache.org/43/streams/architecture/)
- [Kafka Streams configuration: exactly-once processing and state durability](https://kafka.apache.org/43/streams/developer-guide/config-streams/)
- [Queue-based load leveling: buffering bursts and bounding downstream load](https://learn.microsoft.com/en-us/azure/architecture/patterns/queue-based-load-leveling)
- [Event sourcing: accepted events, replay, snapshots, concurrency, and event-store requirements](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
- [CQRS: separating models for changes and queries](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)
- [PostgreSQL transactions: committing several changes atomically](https://www.postgresql.org/docs/current/tutorial-transactions.html)
- [PostgreSQL constraints: enforcing unique event identities](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-UNIQUE-CONSTRAINTS)
- [Redis data types: shared application state and counters](https://redis.io/docs/latest/develop/data-types/)
- [Amazon S3 objects: storing bytes under object keys](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingObjects.html)
- [Confluent S3 sink connector: exporting Kafka records to object files](https://docs.confluent.io/kafka-connectors/s3-sink/current/overview.html)
- [Amazon S3 Lifecycle: independent object retention, transitions, and expiration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [Amazon CloudFront: delivering web content through edge locations](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html)
