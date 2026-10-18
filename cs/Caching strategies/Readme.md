# Caching strategies

<sub>[Back to Computer Science](../Readme.md#content)</sub>

# Front

How do Cache Aside, Read Through, Write Through, Write Back, and Write Around move data between an application, a cache, and a database?

# Back

**Caching strategies decide who loads missing data and when writes reach the database.** A cache holds data for faster reads; a **hit** finds it, a **miss** does not.

Approximate popularity order for distributed application caches: AWS identifies Cache Aside as most common; positions 2–5 are editorial estimates, not measured adoption. Read and write policies can be combined. Read each sequence top to bottom; dashed arrows are replies.

## 1. Cache Aside

**The application loads the cache.** It checks the cache; on a miss, it reads the database, caches the result, then returns it. On writes, commonly update the database and invalidate (remove) the cached copy. Useful for repeated reads of slowly changing data; misses are slower and concurrent requests can still serve stale data. Below: a cache miss.

![cache-aside.svg](images/cache-aside.svg)

## 2. Read Through

**The cache layer loads missing data.** The application reads through it; on a miss, a loader fetches from the database, fills the cache, and returns the value. This moves loading logic out of the caller but requires a configured loader. Misses still wait for the database. Pair with a write policy to manage updates. Below: a cache miss.

![read-through.svg](images/read-through.svg)

## 3. Write Through

**A write succeeds only after both stores are updated.** Below, the application writes through a cache layer that saves to the database and updates the cache before replying. Reads can use the updated cache, but every write waits for the database and may cache rarely read data. Partial failures still need handling; this is not automatically an atomic transaction across both stores.

![write-through.svg](images/write-through.svg)

## 4. Write Back

**Acknowledge the cache update; persist later.** Also called **write-behind**. A background writer sends queued changes to the database, possibly in batches. This reduces write latency and can reduce database work, but the database temporarily lags. Losing unpersisted cache data can lose acknowledged writes. Below: success returns before the database write.

![write-back.svg](images/write-back.svg)

## 5. Write Around

**Write to the database without filling the cache.** Invalidate any older cached copy; a later read miss loads the new value using Cache Aside or Read Through. This avoids filling the cache with rarely read writes, but the first later read pays the database cost. It complements a read policy. Below: a write with invalidation; no new value is cached.

![write-around.svg](images/write-around.svg)

# Sources

- [AWS — Caching patterns: Cache Aside popularity and Write Through tradeoffs](https://docs.aws.amazon.com/whitepapers/latest/database-caching-strategies-using-redis/caching-patterns.html)
- [Microsoft Azure — Cache-Aside pattern, invalidation, and consistency limits](https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside)
- [Oracle Coherence — Read-Through, Write-Through, and Write-Behind caching](https://docs.oracle.com/cd/E14039_01/coh.320/coh32ug/read_through.htm)
- [Hazelcast — Synchronous and asynchronous writes to an external store](https://docs.hazelcast.com/hazelcast/5.1/data-structures/working-with-external-data)
- [Redis — Cache layer patterns, Write Around, combinations, and failure tradeoffs](https://redis.io/blog/cache-layer-architecture-guide/)
