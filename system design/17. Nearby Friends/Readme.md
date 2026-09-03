# Chapter 17: Nearby Friends
<sub>[Back to System Design](../Readme.md#content)</sub>

## Introduction

This chapter focuses on designing a scalable backend for an application that enables users to share their locations and discover friends who are **nearby**.

The major difference with the proximity chapter is that in this problem, **locations constantly change**, whereas in that one, business addresses more or less stay the same.

---

## Step 1: Understand the Problem and Establish Design Scope

Some questions to drive the interview:
 * C: How geographically close is considered to be "nearby"?
 * I: 5 miles; this number should be configurable.
 * C: Is distance calculated as straight-line distance rather than taking into consideration, for example, a river between friends?
 * I: Yes, that is a reasonable assumption
 * C: How many users does the app have?
 * I: 1 billion users, and 10% of them use the nearby friends feature.
 * C: Do we need to store location history?
 * I: Yes, it can be valuable for, e.g., machine learning.
 * C: Can we assume inactive friends will disappear from the feature in 10 minutes?
 * I: Yes
 * C: Do we need to worry about GDPR, etc.?
 * I: No, for simplicity's sake

### **Functional requirements**

 * Users should be able to see nearby friends on their mobile app. Each friend has a distance and timestamp indicating when the location was updated.
 * The nearby friends list should be updated every few seconds.

### **Non-functional requirements**

- **Low latency**: It's important to receive location updates without too much delay.
- **Reliability**: Occasional data point loss is acceptable, but the system should be generally available.
- **Eventual consistency**: The location data store doesn't need strong consistency. A few seconds' delay in receiving location data in different replicas is acceptable.

### **Back-of-the-envelope**

Some estimations to determine potential scale:
 * Nearby friends are friends within a 5-mile radius.
 * The location refresh interval is 30 seconds. Human walking speed is slow; hence, there is no need to update location too frequently.
 * On average, 100 million users use the feature every day, with 10% concurrent users, i.e., 10 million.
 * On average, a user has 400 friends, all of them use the nearby friends feature
 * App displays 20 nearby friends per page
 * **Location Update QPS** = 10 million / 30 = ~334,000 updates per second

---

## Step 2: Propose High-Level Design and Get Buy-In

Before exploring API and data model design, we'll study the communication protocol we'll use, as it's less ubiquitous than the traditional request-response communication model.

### **High-level design**

At a high level, we'd want to establish effective message passing between peers. This can be done via a peer-to-peer protocol, but that's not practical for a mobile app with a flaky connection and tight power-consumption constraints.

A more practical approach is to use a shared backend as a fan-out mechanism towards friends you want to reach:

<div style="margin-left:3rem">
    <img src="./images/fan-out-backend.svg" alt="fan-out-backend" width="500" />
</div>

What does the backend do?
 * Receives location updates from all active users
 * For each location update, find all active users who should receive it and forward it to them.
 * Do not forward location data if the distance between friends is beyond the configured threshold.

This sounds simple but the challenge is to design the system for the scale we're operating with.

We'll start with a simpler design at first and discuss a more advanced approach in the deep dive:

<div style="margin-left:3rem">
    <img src="./images/simple-high-level-design.svg" alt="simple-high-level-design" width="500" />
</div>

- **Load balancer**: spreads traffic across REST API servers as well as bidirectional WebSocket servers.
- **REST API servers**: handle auxiliary tasks such as managing friends, updating profiles, etc.
- **WebSocket servers**: stateful servers that forward location update requests to respective clients. They also seed the mobile client with nearby friends' locations at initialization (discussed in detail later).
- **Redis location cache**: used to store the most recent location data for each active user. There is a TTL set on each entry in the cache. When the TTL expires, the user is no longer active, and their data is removed from the cache.
- **User database**: stores user and friendship data. Either a relational or NoSQL database can be used for this purpose.
- **Location history database**: stores a history of user location data that is not necessarily used directly within the nearby friends feature, but is instead used for analytical purposes.
- **Redis Pub/Sub**: used as a lightweight message bus that enables different topics for each user channel for location updates.

<div style="margin-left:3rem">
    <img src="./images/redis-pubsub-usage.svg" alt="redis-pubsub-usage" width="500" />
</div>

In the above example, WebSocket servers subscribe to channels for the users who are connected to them and forward location updates to the appropriate users whenever they receive them.

### **Periodic location update**

Here's how the periodic location update flow works:

<div style="margin-left:3rem">
    <img src="./images/periodic-location-update.svg" alt="periodic-location-update" width="500" />
</div>

 * Mobile client sends a location update to the load balancer
 * Load balancer forwards location update to the websocket server's persistent connection for that client
 * Websocket server saves location data to location history database
 * Location data is updated in location cache. Websocket server also saves location data in-memory for subsequent distance calculations for that user
 * The WebSocket server publishes location data in the user's channel via Redis Pub/Sub.
 * Redis Pub/Sub broadcasts the location update to all subscribers for that user channel, i.e., servers responsible for the friends of that user.
 * Subscribed WebSocket servers receive the location update, calculate which users it should be sent to, and send it.

Here's a more detailed version of the same flow:

<div style="margin-left:3rem">
    <img src="./images/detailed-periodic-location-update.svg" alt="detailed-periodic-location-update" width="500" />
</div>

On average, there are going to be 40 location updates to forward, as a user has 400 friends on average and 10% of them are online at a time.

### **API Design**

WebSocket routines we'll need to support:
 * periodic location update - user sends location data to the WebSocket server
 * client receives location update - server sends friend location data and timestamp
 * websocket client initialization - client sends user location, server sends back nearby friends location data
 * Subscribe to a new friend - the WebSocket server sends a friend ID that the mobile client is supposed to track, e.g., when the friend appears online for the first time
 * Unsubscribe from a friend - the WebSocket server sends a friend ID that the mobile client is supposed to unsubscribe from due to, e.g., the friend going offline

HTTP API - traditional request/response payloads for auxiliary responsibilities.

### **Data model**

 * The location cache will store a mapping between `user_id` and `lat, long, timestamp`. Redis is a great choice for this cache, as we only care about the current location, and it supports the TTL eviction that we need for our use case.
 * The location history table stores the same data but in a relational table with the four columns stated above. Cassandra can be used for this data, as it is optimized for write-heavy loads.

---

## Step 3: Design Deep Dive

Let's discuss how we scale the high-level design so that it works at the scale we're targeting.

### **How well does each component scale?**

- **API servers**: can be easily scaled via autoscaling groups and replicating server instances
- **WebSocket servers**: we can easily scale out the WebSocket servers, but we need to ensure we gracefully shut down existing connections when tearing down a server. E.g., we can mark a server as "draining" in the load balancer and stop sending connections to it prior to its final removal from the server pool.
- **Client initialization**: when a client first connects to a server, it fetches the user's friends, subscribes to their channels on redis pubsub, fetches their location from cache and finally forwards to client
- **User database**: We can shard the database based on user_id. It might also make sense to expose user/friends data via a dedicated service and API, managed by a dedicated team
- **Location cache**: We can shard the cache easily by spinning up several redis nodes. Also, the TTL puts a limit on the max memory we could have taken up at a time. But we still want to handle the large write load
- **Redis Pub/Sub server**: We leverage the fact that no memory is consumed if channels are initialized but not in use. Hence, we can preallocate channels for all users who use the nearby friends feature to avoid having to deal with, e.g., bringing up a new channel when a user comes online and notifying active WebSocket servers.

### **Scaling deep-dive on redis pub/sub component**

We will need around 200gb of memory to maintain all pub/sub channels. This can be achieved by using 2 redis servers with 100gb each.

Given that we need to push ~14 million location updates per second, however, we will need at least 140 Redis servers to handle that load, assuming that a single server can handle ~100,000 pushes per second.

Hence, we'll need a distributed redis server cluster to handle the intense CPU load.

In order to support a distributed redis cluster, we'll need to utilize a service discovery component, such as zookeeper or etcd, to keep track of which servers are alive.

What we need to encode in the service discovery component is this data:

<div style="margin-left:3rem">
    <img src="./images/channel-distribution-data.svg" alt="channel-distribution-data" width="500" />
</div>

WebSocket servers use that encoded data, fetched from ZooKeeper, to determine where a particular channel lives. For efficiency, the hash-ring data can be cached in memory on each WebSocket server.

In terms of scaling the server cluster up or down, we can set up a daily job to scale the cluster as needed based on historical traffic data. We can also overprovision the cluster to handle spikes in load.

The redis cluster can be treated as a stateful storage server as there is some state maintained for the channels and there is a need for coordination with subscribers so that they hand-off to newly provisioned nodes in the cluster.

We have to be mindful of some potential issues during scaling operations:
 * There will be a lot of resubscription requests from the web socket servers due to channels being moved around
 * Some location updates from clients might be missed during the operation, which is acceptable for this problem, but we should still minimize it. Consider doing such an operation when traffic is at its lowest point of the day.
 * We can leverage consistent hashing to minimize the number of channels moved when adding or removing servers.

<div style="margin-left:3rem">
    <img src="./images/consistent-hashing.svg" alt="consistent-hashing" width="500" />
</div>

### **Adding/removing friends**

Whenever a friend is added or removed, the WebSocket server responsible for the affected user needs to subscribe to or unsubscribe from the friend's channel.

Since the "nearby friends" feature is part of a larger app, we can assume that a callback on the mobile client side can be registered whenever any of the events occur and the client will send a message to the websocket server to do the appropriate action.

### **Users with many friends**

We can put a cap on the total number of friends one can have; e.g., Facebook has a cap of 5000 friends.

The websocket server handling the "whale" user might have a higher load on its end, but as long as we have enough web socket servers, we should be okay.

### **Nearby random person**

What if the interviewer wants to update the design to include a feature where we can occasionally see a random person pop up on our nearby friends map?

One way to handle this is to define a pool of pubsub channels, based on geohash:

<div style="margin-left:3rem">
    <img src="./images/geohash-pubsub.svg" alt="geohash-pubsub" width="500" />
</div>

Anyone within the geohash subscribes to the appropriate channel to receive location updates for random users:

<div style="margin-left:3rem">
    <img src="./images/location-updates-geohash.svg" alt="location-updates-geohash" width="500" />
</div>

We could also subscribe to several geohashes to handle cases where someone is close but in a bordering geohash:

<div style="margin-left:3rem">
    <img src="./images/geohash-borders.svg" alt="geohash-borders" width="500" />
</div>

### **Alternative to Redis pub/sub**

An alternative to using Redis for pub/sub is to leverage Erlang - a general programming language, optimized for distributed computing applications.

With it, we can spawn millions of small Erlang processes that communicate with each other. We can handle both WebSocket connections and Pub/Sub channels within the distributed Erlang application.

A challenge with using Erlang, though, is that it's a niche programming language, and it could be hard to source strong Erlang developers.

---

## Step 4: Wrap Up

We successfully designed a system that supports the nearby friends feature.

Core components:
- **Web socket servers**: real-time comms between client and server
- **Redis**: fast read and write of location data + pub/sub channels

We also explored how to scale RESTful API servers, WebSocket servers, the data layer, and Redis Pub/Sub servers. We also explored an alternative to using Redis Pub/Sub and a "random nearby person" feature.

## Reference materials

1. [Facebook Launches “Nearby Friends”](https://techcrunch.com/2014/04/17/facebook-nearby-friends/)
2. [Redis Pub/Sub documentation](https://redis.io/docs/latest/develop/pubsub/)
3. [Redis Pub/Sub implementation](https://github.com/redis/redis/blob/unstable/src/pubsub.c)
4. [etcd](https://etcd.io/)
5. [Zookeeper](https://zookeeper.apache.org/)
6. [Consistent hashing](https://www.toptal.com/big-data/consistent-hashing)
7. [Erlang](https://www.erlang.org/)
8. [Elixir](https://elixir-lang.org/)
9. [A brief introduction to BEAM](https://www.erlang.org/blog/a-brief-beam-primer/)
10. [OTP](https://www.erlang.org/doc/design_principles/des_princ.html)
