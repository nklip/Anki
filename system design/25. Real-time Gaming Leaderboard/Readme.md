# Chapter 25: Real-time Gaming Leaderboard
<sub>[Back to System Design](../Readme.md#content)</sub>

## Introduction

We are going to design a **leaderboard** for an online mobile game:

<div style="margin-left:3rem">
    <img src="./images/leaderboard.svg" alt="leaderboard" width="500" />
</div>

---

## Step 1: Understand the Problem and Establish Design Scope

- C: How is the score calculated for the leaderboard?
- I: A user gets a point whenever they win a match.
- C: Are all players included in the leaderboard?
- I: Yes
- C: Is there a time segment associated with the leaderboard?
- I: Each month, a new tournament starts which starts a new leaderboard.
- C: Can we assume we only care about top 10 users?
- I: We want to display the top 10 users, along with the position of a specific user. If time permits, we can discuss showing users around a particular user in the leaderboard.
- C: How many users are in a tournament?
- I: 5 million DAU and 25 million MAU
- C: How many matches are played on average during a tournament?
- I: Each player plays 10 matches per day on average
- C: How do we determine the rank if two players have the same score?
- I: Their rank is the same in that case. If time permits, we can discuss breaking ties.
- C: Does the leaderboard need to be real-time?
- I: Yes, we want to present real-time results, or as close to real time as possible. It is not okay to present batched result history.

### **Functional requirements**

- Display top 10 players on leaderboard
- Show a user's specific rank
- Display users who are four places above and below a given user (bonus)

### **Non-functional requirements**

- Real-time updates on scores
- Score update is reflected on the leaderboard in real-time
- General scalability, availability, reliability

### **Back-of-the-envelope estimation**

With 50 million DAU, if the game has an even distribution of players during a 24-hour period, we'd have an average of 50 users per second.
However, since distribution is typically uneven, we can estimate that the peak online users would be 250 users per second.

QPS for users scoring a point - given 10 games per day on average, 50 users/s * 10 = 500 QPS. Peak QPS = 2500.

QPS for fetching the top 10 leaderboard - assuming users open that once a day on average, QPS is 50.

---

## Step 2: Propose High-Level Design and Get Buy-In

### **API Design**

The first API we need is one to update a user's score:

```http
POST /v1/scores
```

This API takes two params - `user_id` and `points` scored for winning a game.

This API should only be accessible to game servers, not end clients.

Next one is for getting the top 10 players of the leaderboard:

```http
GET /v1/scores
```

Example response:

```json
{
  "data": [
    {
      "user_id": "user_id1",
      "user_name": "alice",
      "rank": 1,
      "score": 12543
    },
    {
      "user_id": "user_id2",
      "user_name": "bob",
      "rank": 2,
      "score": 11500
    }
  ],
  ...
  "total": 10
}
```

You can also get the score of a particular user:

```http
GET /v1/scores/{:user_id}
```

Example response:

```json
{
    "user_info": {
        "user_id": "user5",
        "score": 1000,
        "rank": 6
    }
}
```

### **High-level architecture**

<div style="margin-left:3rem">
    <img src="./images/high-level-architecture.svg" alt="high-level-architecture" width="500" />
</div>

- When a player wins a game, the client sends a request to the game service.
- The game service validates whether the win is valid and calls the leaderboard service to update the player's score.
- The leaderboard service updates the user's score in the leaderboard store.
- The player calls the leaderboard service to fetch leaderboard data, e.g., the top 10 players and the given player's rank.

An alternative design which was considered is the client updating their score directly within the leaderboard service:

<div style="margin-left:3rem">
    <img src="./images/alternative-design.svg" alt="alternative-design" width="500" />
</div>

This option is not secure as it's susceptible to man-in-the-middle attacks. Players can put a proxy and change their score as they please.

One additional caveat is that for games where the game logic is managed by the server, clients don't need to call the server explicitly to record their win.
Servers do it automatically for them based on the game logic.

One additional consideration is whether we should put a message queue between the game server and the leaderboard service. This would be useful if other services are interested in game results, but that is not an explicit requirement in the interview so far, hence it's not included in the design:

<div style="margin-left:3rem">
    <img src="./images/message-queue-based-comm.svg" alt="message-queue-based-comm" width="500" />
</div>

### **Data models**

Let's discuss the options we have for storing leaderboard data - relational DBs, Redis, NoSQL.

The NoSQL solution is discussed in the deep dive section.

#### Relational database solution

If the scale doesn't matter and we don't have that many users, a relational DB serves us quite well.

We can start from a simple leaderboard table, one for each month (personal note - this doesn't make sense. You can just add a `month` column and avoid the headache of maintaining new tables each month):

<div style="margin-left:3rem">
    <img src="./images/leaderboard-table.svg" alt="leaderboard-table" width="500" />
</div>

There is additional data to include in there, but that is irrelevant to the queries we'd run, so it's omitted.

What happens when a user wins a point?

<div style="margin-left:3rem">
    <img src="./images/user-wins-point.svg" alt="user-wins-point" width="500" />
</div>

If a user doesn't exist in the table yet, we need to insert them first:

```sql
INSERT INTO leaderboard (user_id, score) VALUES ('mary1934', 1);
```

On subsequent calls, we'd just update their score:

```sql
UPDATE leaderboard set score=score + 1 where user_id='mary1934';
```

How do we find the top players of a leaderboard?

<div style="margin-left:3rem">
    <img src="./images/find-leaderboard-position.svg" alt="find-leaderboard-position" width="500" />
</div>

We can run the following query:

```sql
SELECT (@rownum := @rownum + 1) AS rank, user_id, score
FROM leaderboard
ORDER BY score DESC;
```

This is not performant, though, as it makes a table scan to order all records in the database table.

We can optimize it by adding an index on `score` and using the `LIMIT` operation to avoid scanning everything:

```sql
SELECT (@rownum := @rownum + 1) AS rank, user_id, score
FROM leaderboard
ORDER BY score DESC
LIMIT 10;
```

This approach, however, doesn't scale well if the user is not at the top of the leaderboard and you'd want to locate their rank.

#### Redis solution

We want to find a solution that works well even for millions of players without having to fall back on complex database queries.

Redis is an in-memory data store, which is fast as it works in-memory and has a suitable data structure to serve our needs - sorted set.

A sorted set is a data structure similar to sets in programming languages that allows you to keep data sorted by a given criterion.
Internally, it is implemented using a hash-map to maintain mapping between key (user_id) and value (score) and a skip list which maps scores to users in sorted order:

<div style="margin-left:3rem">
    <img src="./images/sorted-set.svg" alt="sorted-set" width="500" />
</div>

How does a skip list work?
- It is a linked list which allows for fast search
- It consists of a sorted linked list and multi-level indexes

<div style="margin-left:3rem">
    <img src="./images/skip-list.svg" alt="skip-list" width="500" />
</div>

This structure enables us to quickly search for specific values when the data set is large enough.
In the example below (64 nodes), it requires traversing 62 nodes in a base linked list to find the given value and 11 nodes in the skip-list case:

<div style="margin-left:3rem">
    <img src="./images/skip-list-performance.svg" alt="skip-list-performance" width="500" />
</div>

Sorted sets are more performant than relational databases as the data is kept sorted at all times at the price of O(logN) add and find operation.

In contrast, here's an example nested query we need to run to find the rank of a given user in a relational DB:

```sql
SELECT *,(SELECT COUNT(*) FROM leaderboard lb2
WHERE lb2.score >= lb1.score) RANK
FROM leaderboard lb1
WHERE lb1.user_id = {:user_id};
```

What operations do we need to operate our leaderboard in Redis?
- **ZADD** - insert the user into the set if they don't exist. Otherwise, update the score. O(logN) time complexity.
- **ZINCRBY** - increment the score of a user by given amount. If user doesn't exist, score starts at zero. O(logN) time complexity.
- **ZRANGE/ZREVRANGE** - fetch a range of users, sorted by their score. We can specify order (ASC/DESC), offset and result size. O(logN+M) time complexity where M is result size.
- **ZRANK/ZREVRANK** - Fetch the position (rank) of a given user in ASC/DESC order. O(logN) time complexity.

What happens when a user scores a point?

```text
ZINCRBY leaderboard_feb_2021 1 'mary1934'
```

There's a new leaderboard created every month while old ones are moved to historical storage.

What happens when a user fetches the top 10 players?

```text
ZREVRANGE leaderboard_feb_2021 0 9 WITHSCORES
```

Example result:

```text
[(user2,score2),(user1,score1),(user5,score5)...]
```

What about a user fetching their leaderboard position?

<div style="margin-left:3rem">
    <img src="./images/leaderboard-position-of-user.svg" alt="leaderboard-position-of-user" width="500" />
</div>

This can be easily achieved by the following query, given that we know a user's leaderboard position:

```text
ZREVRANGE leaderboard_feb_2021 357 365
```

A user's position can be fetched using `ZREVRANK <user-id>`.

Let's explore what our storage requirements are:
- Assuming a worst-case scenario of all 25 million MAU participating in the game for a given month.
- The ID is a 24-character string, and the score is a 16-bit integer, so we need 26 bytes * 25 million = ~650 MB of storage.
- Even if we double the storage cost due to the overhead of the skip list, this would still easily fit in a modern Redis cluster.

Another non-functional requirement to consider is supporting 2500 updates per second. This is well within a single Redis server's capabilities.

Additional caveats:
- We can spin up a Redis replica to avoid losing data when a Redis server crashes.
- We can still leverage Redis persistence to not lose data in the event of a crash
- We'll need two supporting tables in MySQL to fetch user details such as username, display name, etc., as well as store when, e.g., a user won a game.
- The second table in MySQL can be used to reconstruct leaderboard when there is an infrastructure failure
- As a small performance optimization, we could cache the user details of top 10 players as they'd be frequently accessed

---

## Step 3: Design Deep Dive

### **To use a cloud provider or not**

We can either choose to deploy and manage our own services or use a cloud provider to manage them for us.

If we choose to manage the services ourselves, we'll use Redis for leaderboard data, MySQL for user profiles, and potentially a cache for user profiles if we want to scale the database:

<div style="margin-left:3rem">
    <img src="./images/manage-services-ourselves.svg" alt="manage-services-ourselves" width="500" />
</div>

Alternatively, we could use cloud offerings to manage a lot of the services for us. For example, we can use AWS API Gateway to route API calls to AWS Lambda functions:

<div style="margin-left:3rem">
    <img src="./images/api-gateway-mapping.svg" alt="api-gateway-mapping" width="500" />
</div>

AWS Lambda enables us to run code without managing or provisioning servers ourselves. It runs only when needed and scales automatically.

Example of a user scoring a point:

<div style="margin-left:3rem">
    <img src="./images/user-scoring-point-lambda.svg" alt="user-scoring-point-lambda" width="500" />
</div>

Example user retrieving leaderboard:

<div style="margin-left:3rem">
    <img src="./images/user-retrieve-leaderboard.svg" alt="user-retrieve-leaderboard" width="500" />
</div>

Lambdas are an implementation of a serverless architecture. We don't need to manage scaling and environment setup.

Author recommends going with this approach if we build the game from the ground up.

### **Scaling Redis**

With 5 million DAU, we can get away with a single Redis instance from both a storage and QPS perspective.

However, if we imagine the user base grows 10x to 500 million DAU, then we'd need 65 GB for storage, and QPS would increase to 250k.

Such scale would require sharding.

One way to achieve it is by range-partitioning the data:

<div style="margin-left:3rem">
    <img src="./images/range-partition.svg" alt="range-partition" width="500" />
</div>

In this example, we'll shard based on user's score. We'll maintain the mapping between user_id and shard in application code.
We can do that either via MySQL or another cache for the mapping itself.

To fetch the top 10 players, we'd query the shard with the highest scores (`[900-1000]`).

To fetch a user's rank, we'll need to calculate the rank within the user's shard and add up all users with higher scores in other shards.
The latter is an O(1) operation, as total records per shard can quickly be accessed via the `INFO keyspace` command.

Alternatively, we can use hash partitioning via Redis Cluster. It is a proxy which distributes data across redis nodes based on partitioning similar to consistent hashing, but not exactly the same:

<div style="margin-left:3rem">
    <img src="./images/hash-partition.svg" alt="hash-partition" width="500" />
</div>

Calculating the top 10 players is challenging with this setup. We'll need to get the top 10 players of each shard and merge the results in the application:

<div style="margin-left:3rem">
    <img src="./images/top-10-players-calculation.svg" alt="top-10-players-calculation" width="500" />
</div>

There are some limitations with the hash partitioning:
- If we need to fetch the top K users where K is high, latency can increase, as we'll need to fetch a lot of data from all the shards.
- Latency increases as the number of partitions grows
- There is no straightforward approach to determine a user's rank

Due to all this, the author leans towards using fixed partitions for this problem.

Other caveats:
- A best practice is to allocate twice as much memory as required for write-heavy redis nodes to accommodate snapshots if required
- We can use a tool called Redis-benchmark to track the performance of a Redis setup and make data-driven decisions.

### **Alternative solution: NoSQL**

An alternative solution to consider is using an appropriate NoSQL database optimized for:
- heavy writes
- effectively sorting items within the same partition by score

DynamoDB, Cassandra or MongoDB are all good fits.

In this chapter, the author has decided to use DynamoDB. It is a fully managed NoSQL database that offers reliable performance and great scalability.
It also enables usage of global secondary indexes when we need to query fields not part of the primary key.

<div style="margin-left:3rem">
    <img src="./images/dynamo-db.svg" alt="dynamo-db" width="500" />
</div>

Let's start from a table for storing a leaderboard for a chess game:

<div style="margin-left:3rem">
    <img src="./images/chess-game-leaderboard-table-1.svg" alt="chess-game-leaderboard-table-1" width="500" />
</div>

This works well, but doesn't scale well if we need to query anything by score. Hence, we can put the score as a sort key:

<div style="margin-left:3rem">
    <img src="./images/chess-game-leaderboard-table-2.svg" alt="chess-game-leaderboard-table-2" width="500" />
</div>

Another problem with this design is that we're partitioning by month. This leads to a hotspot partition as the latest month will be unevenly accessed compared to the others.

We could use a technique called write sharding, where we append a partition number for each key, calculated via `user_id % num_partitions`:

<div style="margin-left:3rem">
    <img src="./images/chess-game-leaderboard-table-3.svg" alt="chess-game-leaderboard-table-3" width="500" />
</div>

An important trade-off to consider is how many partitions we should use:
- The more partitions there are, the higher the write scalability
- However, read scalability suffers as we need to query more partitions to collect aggregate results

Using this approach requires that we use the "scatter-gather" technique we saw earlier, which grows in time complexity as we add more partitions:

<div style="margin-left:3rem">
    <img src="./images/scatter-gather-2.svg" alt="scatter-gather-2" width="500" />
</div>

To make a good evaluation on the number of partitions, we'd need to do some benchmarking.

This NoSQL approach still has one major downside - it is hard to calculate the specific rank of a user.

If we have sufficient scale to require us to shard, we could then perhaps tell users what "percentile" of scores they're in.

A cron job can periodically run to analyze score distributions, based on which a user's percentile is determined, for example:

```text
10th percentile = score < 100
20th percentile = score < 500
...
90th percentile = score < 6500
```

---

## Step 4: Wrap Up

Other things to discuss if time permits:
- **Faster retrieval** - We can cache the user object via a Redis hash with mapping `user_id -> user object`. This enables faster retrieval vs. querying the database.
- **Breaking ties** - When two players have the same score, we can break the tie by sorting them based on last played game.
- **System failure recovery** - In the event of a large-scale Redis outage, we can recreate the leaderboard by going through the MySQL WAL entries with an ad hoc script.

## Reference materials

1. [Man-in-the-middle attack](https://en.wikipedia.org/wiki/Man-in-the-middle_attack)
2. [Redis Sorted Set source code](https://github.com/redis/redis/blob/unstable/src/t_zset.c)
3. [Geekbang](https://static001.geekbang.org/resource/image/46/a9/46d283cd82c987153b3fe0c76dfba8a9.jpg)
4. [Building real-time Leaderboard with Redis](https://medium.com/@sandeep4.verma/building-real-time-leaderboard-with-redis-82c98aa47b9f)
5. [Build a real-time gaming leaderboard with Amazon ElastiCache for Redis](https://aws.amazon.com/blogs/database/building-a-real-time-gaming-leaderboard-with-amazon-elasticache-for-redis)
6. [How we created a real-time Leaderboard for a million Users](https://levelup.gitconnected.com/how-we-created-a-real-time-leaderboard-for-a-million-users-555aaa3ccf7b)
7. [Build a real-time leaderboard with Redis](https://redis.io/tutorials/howtos/leaderboard/)
8. [Lambda](https://aws.amazon.com/lambda/)
9. [Google Cloud Functions](https://cloud.google.com/functions)
10. [Azure Functions](https://azure.microsoft.com/en-us/services/functions/)
11. [Info command](https://redis.io/commands/INFO)
12. [Why redis cluster only have 16384 slots](https://stackoverflow.com/questions/36203532/why-redis-cluster-only-have-16384-slots)
13. [Cyclic redundancy check](https://en.wikipedia.org/wiki/Cyclic_redundancy_check)
14. [Choosing your node size](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/nodes-select-size.html)
15. [How fast is Redis?](https://redis.io/topics/benchmarks)
16. [Using Global Secondary Indexes in DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html)
17. [Leaderboard & Write Sharding](https://www.dynamodbguide.com/leaderboard-write-sharding/)
