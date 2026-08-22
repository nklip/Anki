# Locking in Jakarta Persistence and Hibernate

*Updated for Jakarta Persistence 3.2 (Jakarta EE 11) and Hibernate ORM 6.x/7.x.*

**Jakarta Persistence supports optimistic and pessimistic locking.** Pessimistic locking was introduced in JPA 2.0; the API around it was substantially modernised in Jakarta Persistence 3.2.

Hibernate applies **no explicit lock unless you ask for one** — with one important exception: if an entity declares a `@Version` attribute, Hibernate applies implicit optimistic locking on every flush automatically. Otherwise it relies entirely on the database's transaction isolation level.

**Optimistic locking** is Hibernate's invention layered on a version column;  
**Pessimistic locking** is the database's own row-locking, and Hibernate is just a syntax generator for it.

## Optimistic vs. pessimistic vs. isolation

These are three separate mechanisms and conflating them is the most common source of confusion.

| | Enforced by | Detects conflict | Blocks other transactions |
|---|---|---|---|
| Transaction isolation | Database | Depends on level | Depends on level |
| Optimistic locking | JPA provider (version column) | At flush | Never |
| Pessimistic locking | Database (`SELECT … FOR UPDATE`) | At lock acquisition | Yes |

Optimistic locking is completely orthogonal to isolation level (i.e. optimistic locking is a separate mechanism from transaction isolation). It does not affect the isolation of concurrent transactions, and the locks the database uses internally to implement isolation continue to work regardless of whether JPA locking is enabled.

Its real purpose is covering the gap that isolation cannot cover: a conversation that spans multiple transactions — load an entity in one transaction, present it to a user, save it in another. No isolation level protects that window, because the transactions don't overlap.

## Optimistic locking

### Declaring a version attribute (explicitly, you need to create a version column for your table)

```java
@Entity
public class Product {
    @Id @GeneratedValue private Long id;

    @Version
    private long version;     // recommended
}
```

Permitted types per Jakarta Persistence 3.2:

`int`, `Integer`, `short`, `Short`, `long`, `Long`, `java.sql.Timestamp`, `java.time.Instant`, `java.time.LocalDateTime`

`Instant` and `LocalDateTime` are new in 3.2. In the same release the legacy `java.util.Date` / `Calendar` / `java.sql.*` types were deprecated, so `java.sql.Timestamp` is now the type to avoid.

Prefer a numeric version over a timestamp. Timestamp resolution can be coarser than the interval between two updates, letting a genuine conflict slip through undetected. Use `long`; use `Instant` only when the column must be human-readable.

**Rules:** at most one `@Version` per entity, declared by the root entity of a hierarchy or a mapped superclass, and mapped to the entity's primary table. Never modify it in application code.

### How and when the check happens

On flush, Hibernate emits:

```sql
UPDATE product SET name = ?, version = 6 WHERE id = ? AND version = 5
```

If the update affects zero rows, another transaction has already modified the row and `OptimisticLockException` is thrown.

> **Correction to a common claim:** the check happens at **flush**, not strictly at commit. Flush usually occurs at commit, but an explicit `em.flush()` or a query-triggered auto-flush will surface the failure earlier. This determines where you can actually catch the exception.

### Exceptions you'll see

| Layer | Exception |
|---|---|
| Jakarta Persistence | `OptimisticLockException` |
| Hibernate (native) | `StaleObjectStateException` / `StaleStateException` |
| Spring Data JPA | `ObjectOptimisticLockingFailureException` |

### Optimistic locking is useless without a retry

Detection is only half the pattern. An unhandled `OptimisticLockException` is a failed user request.

```java
@Retryable(retryFor = ObjectOptimisticLockingFailureException.class,
           maxAttempts = 3, backoff = @Backoff(delay = 50, multiplier = 2))
@Transactional
public void adjustStock(Long id, int delta) { … }
```

The retry must re-read the entity inside a new transaction — retrying with the same stale instance fails identically. Add jitter under contention.

### Explicit optimistic lock modes

Two `LockModeType` values are optimistic, and both are missing from most summaries:

- **`OPTIMISTIC`** — verifies at commit that an entity you merely read has not changed. Protects against non-repeatable reads without blocking anyone.
- **`OPTIMISTIC_FORCE_INCREMENT`** — bumps the version even if the entity itself wasn't modified. The standard tool for aggregate roots: modifying a child (an `OrderLine`) can force a version increment on the parent (`Order`), so concurrent edits to different children still conflict.

```java
em.find(Order.class, id, LockModeType.OPTIMISTIC_FORCE_INCREMENT);
```

(`LockModeType.READ` and `WRITE` are deprecated aliases for these two. Don't use them.)

### Hibernate: versionless optimistic locking

For legacy schemas that cannot add a version column:

```java
@Entity
@OptimisticLocking(type = OptimisticLockType.DIRTY)   // or ALL
@DynamicUpdate                                        // required
public class LegacyProduct { … }
```

`DIRTY` adds only the modified columns to the `WHERE` clause; `ALL` adds every column. Both are weaker and slower than a version column, and neither works for detached entities. Use only when you have no choice.

## Pessimistic locking

Use when a conflict is likely enough that **detecting it late is too expensive**, or when you must read-then-write atomically (inventory decrements, ledger balances, job queues).

### The three pessimistic modes

- **`PESSIMISTIC_READ`** — shared lock. Others may read, but not update or delete. Maps to `SELECT … FOR SHARE` (PostgreSQL) or `LOCK IN SHARE MODE` (MySQL). Where a dialect has no shared-lock syntax, Hibernate silently escalates to `FOR UPDATE`.
- **`PESSIMISTIC_WRITE`** — exclusive lock, the one you'll normally want. Maps to `SELECT … FOR UPDATE`.

> ⚠️ **The spec says this prevents other transactions from reading the data. On real databases it does not.** PostgreSQL, MySQL/InnoDB, Oracle, and SQL Server with RCSI all implement MVCC and serve non-locking snapshot reads from an existing row version. `FOR UPDATE` blocks other *locking reads* (`FOR UPDATE` / `FOR SHARE`) and writes — not a plain `SELECT`. This is the normal case, not an Oracle quirk.

- **`PESSIMISTIC_FORCE_INCREMENT`** — as `PESSIMISTIC_WRITE`, plus a version increment, so detached readers holding an older version also detect the change. Requires a versioned entity; on an unversioned one the provider may throw `PersistenceException`.

### Acquiring a lock

```java
// at load time — one statement, no race
Product p = em.find(Product.class, id, LockModeType.PESSIMISTIC_WRITE);

// on an already-managed entity — emits a second statement
em.lock(p, LockModeType.PESSIMISTIC_WRITE);

// in a query
em.createQuery("from Product p where p.sku = :sku", Product.class)
  .setParameter("sku", sku)
  .setLockMode(LockModeType.PESSIMISTIC_WRITE)
  .getSingleResult();
```

```java
// Spring Data JPA
public interface ProductRepository extends JpaRepository<Product, Long> {
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    Optional<Product> findBySku(String sku);
}
```

Prefer locking at `find()` time. Locking afterwards leaves a window in which another transaction can modify the row.

### Timeouts — Jakarta Persistence 3.2's type-safe options

Without a timeout a blocked lock waits indefinitely (or until the database's own deadlock detector fires). 3.2 **replaced** the string-hint API with type-safe `FindOption` / `LockOption` / `RefreshOption`:

```java
// Jakarta Persistence 3.2 and later
var p = em.find(Product.class, id,
                LockModeType.PESSIMISTIC_WRITE,
                Timeout.seconds(5));

// legacy string-hint form
em.find(Product.class, id, LockModeType.PESSIMISTIC_WRITE,
        Map.of("jakarta.persistence.lock.timeout", 5000));
```

Note the javadoc caveat: `Timeout` is **always a hint and may be ignored by the provider** — behaviour depends on dialect support.

Two special values matter in practice:

- **`NOWAIT` (timeout 0)** — fail immediately rather than queue. Good for interactive requests where a spinner beats a hung thread.
- **`SKIP LOCKED`** — skip rows another transaction holds. The idiomatic way to build a job queue on a relational database:

```java
em.createQuery("from Job j where j.status = 'PENDING' order by j.createdAt", Job.class)
  .setMaxResults(10)
  .setLockMode(LockModeType.PESSIMISTIC_WRITE)
  .setHint(AvailableHints.HINT_SPEC_LOCK_TIMEOUT, "-2")   // Hibernate: SKIP_LOCKED
  .getResultList();
```

### Lock scope

`PessimisticLockScope.NORMAL` (default) locks the entity's own table rows. `PessimisticLockScope.EXTENDED` additionally locks rows in join tables and collection tables. Note that the database may escalate row locks to page or table locks under load — "one lock per object" is a JPA-level abstraction, not a physical guarantee.

### Exceptions

| Situation | Exception |
|---|---|
| Lock could not be obtained; transaction marked for rollback | `PessimisticLockException` |
| Lock timed out; transaction still usable | `LockTimeoutException` |

Distinguishing them matters: only `LockTimeoutException` is safely retryable within the same transaction.

### Deadlocks

Pessimistic locking trades conflict-detection cost for deadlock risk. Two mitigations:

1. Acquire locks in a consistent global order across all code paths (e.g. always ascending by primary key).
2. Keep locked sections short. Never hold a pessimistic lock across a network call, a user interaction, or a message-broker publish.

## Choosing

| Situation | Use |
|---|---|
| Conversation spanning transactions (edit form, detached entity) | `@Version` + retry |
| Low-contention CRUD | `@Version` |
| Read-modify-write on a hot row (stock, balance) | `PESSIMISTIC_WRITE` |
| Job queue / work claiming | `PESSIMISTIC_WRITE` + `SKIP LOCKED` |
| Child edit must conflict with concurrent parent edit | `OPTIMISTIC_FORCE_INCREMENT` |
| Read must stay valid until commit, without blocking | `OPTIMISTIC` |
| Legacy schema, no version column possible | `@OptimisticLocking(type = DIRTY)` |

**Default to optimistic.** Reach for pessimistic locking when you have measured contention, not in anticipation of it — and always with a timeout.
