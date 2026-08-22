# Garbage Collection: G1

## Front

How does the **Garbage-First (G1) collector** work, how does it organize heap memory, and how do young, concurrent-marking, and mixed collections reclaim space?

## Back

**G1**, or Garbage-First, is HotSpot's region-based, generational, incremental, parallel, mostly concurrent, evacuating garbage collector.

G1 aims to balance throughput with predictable pauses. It tries to meet a configurable pause-time goal by choosing how many heap regions to collect during each stop-the-world pause.

G1 is the default collector on server-class HotSpot configurations in Java 25 and Java 26.

```bash
# Usually selected automatically on a server-class machine
java -jar application.jar

# Select it explicitly
java -XX:+UseG1GC -jar application.jar
```

### Main characteristics

- **Generational:** objects are grouped logically into young and old generations.
- **Region-based:** the heap is divided into equally sized regions.
- **Non-contiguous generations:** Eden, survivor, and old regions may be scattered throughout the heap.
- **Evacuating and compacting:** live objects are copied out of selected regions, compacting them in destination regions.
- **Incremental:** G1 reclaims selected regions rather than compacting the whole heap in every collection.
- **Parallel:** multiple GC threads perform work during collection pauses.
- **Mostly concurrent:** old-generation liveness marking runs mostly alongside the application.
- **Adaptive:** G1 changes young-generation size and collection-set size based on measured pause costs.

> G1 is not fully concurrent. Its normal space-reclamation mechanism—evacuating live objects from selected regions—occurs during stop-the-world pauses.

## Memory organization

![G1 memory organization](svg/gc-g1-memory-organization.svg)

### Equal-sized heap regions

G1 partitions the Java heap into many equally sized regions. Each region is a contiguous range of virtual memory and is the basic unit of allocation and reclamation.

```text
Java heap

| region | region | region | region | ... | region |
```

At a particular moment, a region may be:

- **Free** — available for assignment.
- **Eden** — receives most new object allocations.
- **Survivor** — contains young objects that survived a young collection.
- **Old** — contains promoted or long-lived objects.
- **Humongous start/continuation** — stores an unusually large object across contiguous regions.

The JVM chooses region size ergonomically from the maximum heap size, targeting roughly 2,048 regions. In Java 26 the automatic size is capped at 32 MB, while an explicitly configured region size must be a power of two from 1 MB through 512 MB:

```bash
-XX:G1HeapRegionSize=8m
```

Region size should normally be left to G1. Changing it affects remembered-set cost, evacuation granularity, and which objects are classified as humongous.

### Generations are logical sets of regions

The young and old generations do not have to occupy two continuous areas:

```text
Physical region order:

| Eden | Old | Free | Survivor | Old | Eden | Old | Free |

Logical young generation = Eden + Survivor regions
Logical old generation   = Old + Humongous regions
```

G1 can reassign a free region to the role currently required. This lets the young generation grow or shrink without moving a fixed boundary between contiguous young and old spaces.

### Eden allocation

Normal objects are allocated into Eden regions, commonly through thread-local allocation buffers inside Eden:

```text
Application allocation
        ↓
thread-local allocation buffer
        ↓
Eden region
```

When G1 reaches its chosen young-generation size, it performs a young evacuation pause.

Humongous objects are an important exception: they are allocated directly into contiguous regions treated as part of the old generation.

### Region lifecycle

```text
Free
  ↓ assign for allocation
Eden
  ↓ survives a young collection
Survivor
  ↓ survives enough collections
Old
  ↓ selected and successfully evacuated
Free
```

The exact path is adaptive. A young object may be promoted directly to old if it has reached the tenuring threshold or if survivor capacity is insufficient.

## Young evacuation collection

A normal young collection is a **stop-the-world, parallel evacuation pause**.

The collection set contains the young-generation regions selected for collection—normally the complete current young generation.

```text
Before:

Eden:     [live][dead][dead][live]
Survivor: [live][dead][live]

During the pause:

young live objects ──copy──▶ Survivor or Old

After:

old Eden and Survivor source regions ──▶ Free
```

The destination depends on object age:

- A sufficiently young surviving object is copied to a survivor region.
- An older surviving object is promoted to an old region.
- Dead objects are not copied.

Because live objects are packed into destination regions, evacuation also compacts the collected portion of the heap.

### Why evacuation needs a pause

Unlike ZGC, ordinary G1 does not relocate objects while application threads continue using them. G1 stops application threads, copies objects, updates references, and then resumes the application.

The pause duration therefore depends on work such as:

- Number of regions in the collection set.
- Amount of live data that must be copied.
- Number of references that must be scanned and updated.
- Remembered-set and card-processing work.
- Number of available parallel GC threads.
- Reference processing and operating-system effects.

G1 predicts these costs from previous collections and adjusts young-generation and collection-set sizes to try to meet its pause target.

## Remembered sets and cards

G1 must find references entering a collection set without scanning every object outside it.

For example, an old object may point to a young object:

```text
Old object ─────────▶ object in an Eden region
```

If that Eden region is evacuated, G1 must find and update this reference.

### Card table

G1 divides the heap logically into small **cards**. The default card size is 512 bytes.

When application code writes an object reference, a post-write barrier records that the corresponding card may contain a relevant cross-region reference:

```text
object.field = youngObject;
        ↓
post-write barrier dirties the containing card
```

### Remembered set

A remembered set describes approximate locations outside a collection set that may contain references into it. Entries point to cards rather than recording every individual reference, reducing metadata size.

Concurrent refinement threads process dirty-card information and update remembered-set data while the application runs. Work not completed concurrently may spill into the next collection pause.

At collection time, G1 merges and trims remembered-set information for the selected regions. These incoming-reference locations become heap roots for evacuation.

```text
GC roots
+ code roots
+ remembered-set heap roots
        ↓
trace and evacuate objects in the collection set
```

Remembered sets avoid a complete old-generation scan during every young collection, but they consume memory and CPU and can lengthen pauses when cross-region connectivity is high.

## G1 collection cycle

![G1 collection cycle](svg/gc-g1-collection-cycle.svg)

At a high level, G1 alternates between two phases:

```text
Young-Only phase
        ↓ old occupancy reaches IHOP
Concurrent marking transition
        ↓ identifies profitable old regions
Space-Reclamation phase with Mixed collections
        ↓ no more worthwhile old candidates
Young-Only phase
```

### 1. Young-Only phase

G1 performs normal young evacuation pauses:

```text
Normal Young GC → Normal Young GC → Normal Young GC → ...
```

Surviving objects are copied into survivor or old regions. As promotions accumulate, old-generation occupancy grows.

### 2. Initiating Heap Occupancy threshold

When old-generation occupancy reaches the **Initiating Heap Occupancy Percent**, G1 schedules a **Concurrent Start** collection.

G1 uses Adaptive IHOP by default. It predicts when marking must start from:

- Previous concurrent-marking duration.
- Allocation and promotion rate during marking.
- Available old-generation reserve.

The default initial IHOP value is 45%, but after enough observations the adaptive prediction is more important than that initial number.

### 3. Concurrent Start pause

Concurrent Start is still a young evacuation pause, but it also establishes the snapshot used for old-generation marking.

After the pause, concurrent marking proceeds while application threads run. Normal young collections may still occur during marking.

### 4. Concurrent marking

G1 marks reachable objects in the old generation using **Snapshot-At-The-Beginning (SATB)**.

SATB treats objects reachable at the beginning of marking as live for the current cycle. A pre-write barrier records overwritten references when needed so that concurrent application mutations do not make the collector miss an object from that logical snapshot.

An object that becomes unreachable after the snapshot may remain conservatively considered live until a later cycle.

### 5. Remark pause

The stop-the-world Remark pause:

- Completes marking information.
- Processes reference objects.
- Performs class unloading.
- Reclaims completely empty regions when possible.
- Cleans internal marking data.

G1 calculates liveness and collection efficiency for old regions after marking.

### 6. Cleanup and Prepare Mixed

The Cleanup pause finalizes whether old-generation space reclamation is worthwhile and identifies candidate regions.

If it is worthwhile, G1 performs a Prepare Mixed young collection and enters the Space-Reclamation phase.

### 7. Space-Reclamation phase

G1 performs a sequence of **Mixed collections**:

```text
Mixed GC collection set
= all selected young regions
+ selected old candidate regions
```

Each Mixed collection is a stop-the-world evacuation pause. It reclaims the young generation and a pause-sized subset of old regions.

G1 prefers old regions with:

- Much reclaimable space.
- Relatively little live data to copy.
- Favorable connectivity and predicted collection cost.

This is the “garbage-first” idea: collect regions expected to return the most space for the pause-time cost.

The phase ends when no remaining old candidate is profitable enough to collect. G1 then returns to the Young-Only phase.

## Collection set

The **collection set** is the set of source regions G1 will attempt to reclaim in one pause.

Young collection:

```text
Collection set = young regions
```

Mixed collection:

```text
Collection set = young regions + selected old regions
```

G1 sizes the set using a cost model and the pause-time goal. Mandatory candidate regions ensure progress; extra old regions may be added if predicted time remains, and optional candidates can be attempted if the pause still has room.

Successful evacuation transforms every completely evacuated source region into a free region.

## Humongous objects

An object is **humongous** when its size is at least half of one G1 region.

```text
region size = 8 MB
humongous threshold = 4 MB
```

Humongous allocation differs from normal allocation:

- It goes directly into the old generation rather than Eden.
- It occupies one or more contiguous regions.
- The object begins at the start of the first region.
- Unused space at the end of the final region cannot be used until the complete object is reclaimed.
- G1 normally avoids moving it.

```text
| Humongous start | Humongous continuation | final region + unusable tail |
```

Humongous objects can cause:

- Internal fragmentation in the final region.
- Premature marking cycles.
- Difficulty finding enough contiguous free regions.
- Full GC or `OutOfMemoryError` even when total free bytes appear sufficient.

G1 can reclaim unreachable humongous objects after whole-heap liveness information is available and may opportunistically reclaim some during ordinary pauses. Moving a humongous object is a very slow last-resort operation.

If humongous allocation is a measured problem, investigate the allocation pattern first. Increasing `G1HeapRegionSize` can raise the humongous threshold, but it also makes evacuation coarser and changes remembered-set behavior.

## Pause-time goal

The Java 26 ergonomic default is:

```bash
-XX:MaxGCPauseMillis=200
```

This is a **soft goal**, not a limit or guarantee. G1 uses it to choose young-generation and collection-set sizes.

A lower goal generally causes:

- Smaller young generations.
- More frequent collections.
- Less work per pause.
- Potentially lower throughput.

A higher goal generally allows:

- Larger young generations.
- Less frequent collections.
- More work per pause.
- Potentially higher throughput.

G1 may miss the target when the mandatory work does not fit—for example, because too much live data must be copied, remembered-set processing is large, or the system does not schedule enough CPU time.

## Enabling and observing G1

```bash
java \
  -XX:+UseG1GC \
  -Xmx8g \
  -Xlog:gc*,safepoint \
  -jar application.jar
```

For detailed phase timing:

```bash
-Xlog:gc+phases=debug
```

Useful signals include:

- Young and Mixed pause durations.
- Eden, Survivor, Old, and Humongous region counts.
- Live bytes copied during evacuation.
- Promotion rate and old-generation occupancy.
- Concurrent marking duration.
- `Merge Heap Roots`, `Scan Heap Roots`, and `Object Copy` time.
- Evacuation failures.
- Full GC occurrences.
- Application latency percentiles and throughput.

Java Flight Recorder and Java Mission Control can correlate GC behavior with allocation hot spots and application latency.

## Practical tuning order

G1 is designed to work well with ergonomic defaults. Tune from evidence rather than copying a long option list.

### 1. Set a realistic maximum heap

```bash
-Xmx8g
```

The heap needs room for the live set, allocation bursts, promotion during concurrent marking, and evacuation destination regions.

Too little reserve can produce evacuation failure or Full GC. Too much heap can increase footprint and delay problem detection.

### 2. Adjust the pause goal only if necessary

```bash
-XX:MaxGCPauseMillis=150
```

Measure whether the lower target improves application tail latency without causing excessive GC frequency or throughput loss.

### 3. Avoid fixing young-generation size initially

Explicitly fixing `-Xmn`, `NewSize`, or `MaxNewSize` can prevent G1 from resizing the young generation to meet the pause goal.

Let G1 adapt young size unless measurements prove that a constraint is necessary.

### 4. Investigate Full GC rather than accepting it

Common causes include:

- Concurrent marking starts too late.
- Promotion or allocation outpaces reclamation.
- Too little evacuation reserve.
- Humongous-object fragmentation.
- Pinned objects or insufficient destination space cause evacuation failure.

Possible responses depend on evidence: reduce allocation, increase heap headroom, let marking start earlier, provide more concurrent-marking CPU, or address humongous allocation patterns.

### 5. Change region size only for a demonstrated reason

Larger regions may:

- Reduce the number of cross-region references.
- Reduce the number of objects classified as humongous.
- Increase the amount of live data tied to one evacuation unit.

Smaller regions provide finer-grained collection choices but create more region and remembered-set metadata.

## Evacuation failure and Full GC

An **evacuation failure** means G1 could not move every object from a selected region.

Typical reasons are:

- No sufficient destination space is available.
- An object is pinned and cannot move safely.

The affected region cannot immediately become free. G1 schedules failed regions as high-priority collection candidates for later attempts.

If G1 cannot reclaim enough space, it can fall back to a stop-the-world **Full GC** that performs in-place compaction of the entire heap. This may be very slow and is normally a condition to investigate rather than routine G1 behavior.

## When G1 is a good choice

- General server applications needing a balance of latency and throughput.
- Heaps from moderate sizes to tens of gigabytes or more.
- Workloads with changing allocation and promotion rates.
- Applications that can tolerate pauses around tens or hundreds of milliseconds.
- Systems where a long whole-heap pause from a throughput collector is undesirable.
- Applications that benefit from a mature adaptive default collector.

## When another collector may be better

- Use **ZGC** when extremely short tail latency is the primary objective and additional concurrent overhead is acceptable.
- Use **Parallel GC** for batch workloads where maximum throughput matters and long pauses are acceptable.
- Use **Serial GC** for very small heaps or constrained environments where collector simplicity matters.

## G1 versus ZGC

| Property | G1 | ZGC |
|---|---|---|
| Default on server-class HotSpot | Yes | No |
| Memory organization | Equal-sized regions | Dynamic ZPages / regions |
| Generational | Yes | Yes |
| Global marking | Mostly concurrent | Concurrent |
| Normal object relocation | Stop-the-world | Concurrent |
| Typical objective | Balance latency and throughput | Extremely low pauses |
| Pause sensitivity | Depends on evacuation work | Designed not to scale with heap size |
| Throughput cost | Moderate | Usually higher for the lowest latency |

## Common misconceptions

### “Concurrent G1” means collections do not stop the application

False. Concurrent marking runs alongside the application, but young and Mixed evacuation collections are stop-the-world.

### Young and old generations are contiguous

False. They are logical collections of equal-sized regions scattered through the heap.

### G1 collects one region at a time

False. One pause processes a collection set containing multiple regions. A normal young pause generally collects the entire current young generation.

### `MaxGCPauseMillis` is a hard maximum

False. It is an input to G1's predictive policy, not a real-time guarantee.

### Mixed GC means a Full GC

False. A Mixed GC evacuates young regions plus a selected subset of old regions. Full GC processes and compacts the entire heap as a fallback.

### Every large object is humongous

The classification is relative to region size: an object is humongous at **at least half a region**.

### G1 always has shorter pauses than ZGC

False. ZGC is specifically designed for much shorter pauses because it relocates concurrently. G1 normally offers a different throughput/latency balance.

## Interview summary

> G1 divides the heap into equal-sized regions whose roles—Eden, Survivor, Old, Humongous, or Free—can change dynamically. Normal young collections stop application threads and copy live objects from all young regions into survivor or old regions. Card-based remembered sets find incoming references without scanning the whole heap. When old occupancy reaches an adaptive threshold, G1 concurrently marks the old generation, then performs Mixed evacuation pauses that collect all young regions plus selected garbage-rich old regions. G1 uses a predictive cost model to size each collection set around a soft pause-time goal; Full GC is a slow fallback when incremental evacuation cannot reclaim enough space.

## Official references

- [Oracle JDK 26: Garbage-First Garbage Collector](https://docs.oracle.com/en/java/javase/26/gctuning/garbage-first-g1-garbage-collector1.html)
- [Oracle JDK 26: G1 Garbage Collector Tuning](https://docs.oracle.com/en/java/javase/26/gctuning/garbage-first-garbage-collector-tuning.html)
- [Oracle JDK 26: Garbage Collection Ergonomics](https://docs.oracle.com/en/java/javase/26/gctuning/ergonomics.html)
- [Java 26 launcher and G1 options](https://docs.oracle.com/en/java/javase/26/docs/specs/man/java.html)
