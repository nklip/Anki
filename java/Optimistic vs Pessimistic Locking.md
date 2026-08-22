# Optimistic vs. Pessimistic Locking in Modern Java

## Front

What is the difference between **optimistic** and **pessimistic locking**?

Explain how each strategy works in Java concurrency and databases/Jakarta Persistence, their failure modes and trade-offs, and how to choose between them.

## Back

Both strategies protect shared state from conflicting concurrent updates, but they make different assumptions.

### Optimistic locking

> Assume conflicts are uncommon. Perform work without holding an exclusive lock, then validate that the observed state is still current before committing the change.

```text
read state and version
        ↓
compute proposed change
        ↓
compare expected state/version with current state
        ↓
   unchanged? ── yes → commit atomically
        │
        no
        ↓
abort, reload, merge, or retry
```

### Pessimistic locking

> Assume conflicts are likely or too expensive to tolerate. Acquire a lock before performing the protected operation, and hold it until the operation or transaction completes.

```text
acquire lock
        ↓
read protected state
        ↓
perform operation
        ↓
commit/update
        ↓
release lock
```

The core trade-off is:

```text
optimistic  → no waiting in the common case, but conflicts waste work
pessimistic → prevents conflicting work, but threads/transactions may wait
```

## Quick comparison

| Dimension | Optimistic | Pessimistic |
|---|---|---|
| Assumption | Conflicts are rare | Conflicts are common or costly |
| Coordination time | At validation/commit | Before protected work begins |
| Contending participant | Proceeds, then may fail | Waits, times out, or fails to acquire |
| Main mechanism | Version check, CAS, validation stamp | Monitor, `Lock`, database row/range lock |
| Failure mode | Conflict, failed CAS, retry/abort | Blocking, timeout, deadlock, lock failure |
| Work under conflict | May be repeated or discarded | Usually not duplicated after lock acquisition |
| Deadlock risk | Normally low without multiple held locks | Present when several locks are acquired |
| Starvation risk | Retry starvation under contention | Lock-acquisition starvation depending on policy |
| Best workload | Many reads, short updates, low contention | High contention or expensive/non-repeatable work |
| Side effects | Must not be repeated blindly | Can normally occur once inside the protected section |

“Optimistic locking” is often not a literal lock. It is usually **optimistic concurrency control** based on validation and conditional update.

## In-memory optimistic locking with CAS

Java atomic classes use compare-and-set operations.

```java
record AccountState(long balance) {}

final class Account {
    private final AtomicReference<AccountState> state =
            new AtomicReference<>(new AccountState(0));

    void deposit(long amount) {
        while (true) {
            AccountState current = state.get();
            AccountState next = new AccountState(
                    Math.addExact(current.balance(), amount)
            );

            if (state.compareAndSet(current, next)) {
                return;
            }

            // Another thread changed state; retry from a fresh snapshot.
        }
    }

    long balance() {
        return state.get().balance();
    }
}
```

`compareAndSet(expected, update)` means:

```text
if current reference is exactly expected:
    replace it with update atomically
    return true
else:
    change nothing
    return false
```

The successful CAS is the **linearization point**: the operation takes effect atomically at that moment.

The algorithm is optimistic because it computes `next` assuming `current` remains unchanged. If that assumption becomes false, CAS rejects the update and the loop retries.

### Use immutable candidate state

Do not mutate the shared current object before CAS:

```java
AccountState current = state.get();

// Wrong idea if current were mutable:
current.setBalance(current.getBalance() + amount);
state.compareAndSet(current, current);
```

The mutation would already be visible before validation, and concurrent losers could modify the same object.

Prefer:

```text
read immutable snapshot
        ↓
create a new immutable candidate
        ↓
CAS old reference → new reference
```

### CAS retry functions must be side-effect-free

Atomic update functions may be evaluated more than once when contention causes retries:

```java
state.updateAndGet(current -> calculateNext(current));
```

The function should not:

- Send an email.
- Charge a payment.
- Publish a message.
- Write an audit record externally.
- Consume a one-use token.
- Mutate unrelated shared state.

Keep it deterministic and side-effect-free. Perform external effects only after the state update succeeds, using idempotency or a transactional protocol when a crash between the update and effect matters.

### Retry does not mean unbounded spinning is safe

Under contention, many threads can repeatedly fail CAS and consume CPU:

```text
read → compute → lose CAS → discard → repeat
```

Possible responses include:

- Bounded retries.
- Backoff or jitter.
- Contention reduction or sharding.
- Striped counters such as `LongAdder` for statistics.
- Falling back to a lock.
- Queueing or serializing updates through one owner.

Optimistic algorithms can provide excellent low-contention throughput but degrade into a retry storm under heavy contention.

## ABA problem

CAS validates that the current value or reference equals the expected value at one moment. It may not detect that the state changed away and then returned:

```text
Thread A reads A
Thread B changes A → B → A
Thread A compares with A and succeeds
```

This is the **ABA problem**.

It matters when the intermediate history changes correctness—for example, in some lock-free stacks or resource-state machines.

Possible solutions include:

- An immutable state object with a monotonically increasing version.
- `AtomicStampedReference`.
- `AtomicMarkableReference` for a boolean mark.
- A different algorithm whose correctness does not depend on hidden history.

```java
AtomicStampedReference<Node> head =
        new AtomicStampedReference<>(initial, 0);
```

The reference and stamp can then be validated and changed atomically.

## Optimistic reading with `StampedLock`

`StampedLock` supports an optimistic read mode:

```java
final class Point {
    private double x;
    private double y;
    private final StampedLock lock = new StampedLock();

    double distanceFromOrigin() {
        long stamp = lock.tryOptimisticRead();

        double currentX = x;
        double currentY = y;

        if (!lock.validate(stamp)) {
            stamp = lock.readLock();

            try {
                currentX = x;
                currentY = y;
            } finally {
                lock.unlockRead(stamp);
            }
        }

        return Math.hypot(currentX, currentY);
    }

    void move(double deltaX, double deltaY) {
        long stamp = lock.writeLock();

        try {
            x += deltaX;
            y += deltaY;
        } finally {
            lock.unlockWrite(stamp);
        }
    }
}
```

An optimistic-read stamp is not a held read lock. A writer may modify the state while the fields are being copied.

The safe pattern is:

```text
obtain optimistic stamp
        ↓
copy required fields into locals
        ↓
validate stamp
        ↓
valid? use local snapshot
invalid? acquire real read lock and reread
```

Important `StampedLock` properties:

- `tryOptimisticRead()` can return zero when write-locked.
- `validate(stamp)` must succeed before trusting the optimistic snapshot.
- Fields read before validation may be inconsistent.
- Complex object graphs are dangerous to traverse before validation.
- `StampedLock` is not reentrant.
- It has no ownership model like ordinary `Lock` implementations.
- It does not consistently guarantee reader or writer fairness.

Use optimistic reads only for short, well-understood snapshots that can be copied into locals and safely retried under a real read lock.

## In-memory pessimistic locking

### `synchronized`

```java
final class Counter {
    private int value;

    synchronized void increment() {
        value++;
    }

    synchronized int value() {
        return value;
    }
}
```

Only one thread at a time executes a synchronized method on the same `Counter` instance.

The strategy is pessimistic because a thread acquires exclusive access before reading and changing the protected state.

### `ReentrantLock`

```java
final class Account {
    private final Lock lock = new ReentrantLock();
    private long balance;

    void withdraw(long amount) {
        lock.lock();

        try {
            if (balance < amount) {
                throw new IllegalStateException("Insufficient funds");
            }

            balance -= amount;
        } finally {
            lock.unlock();
        }
    }
}
```

Always release a manually acquired lock in `finally`.

`ReentrantLock` also provides:

- `tryLock()`.
- Timed acquisition.
- Interruptible acquisition.
- Optional fairness policy.
- Multiple `Condition` queues.

A fair lock reduces barging but usually lowers throughput. Fairness still does not guarantee application-level scheduling fairness.

### Shared read and exclusive write locking

`ReentrantReadWriteLock` pessimistically coordinates access while allowing several readers together:

```text
read lock  + read lock  → allowed
read lock  + write lock → blocked
write lock + any lock   → blocked
```

It can help when:

- Read sections are sufficiently long.
- Reads greatly outnumber writes.
- The protected state requires a consistent multi-field snapshot.
- Lock-management overhead is smaller than the benefit of concurrent reads.

For tiny critical sections, an ordinary lock can be faster and much simpler.

## Pessimistic lock failure modes

### Blocking and lock convoy

One slow owner makes all contenders wait:

```text
slow thread holds lock
        ↓
waiting queue grows
        ↓
latency and throughput deteriorate
```

Do not perform avoidable network calls, long disk operations, user interaction, or unbounded callbacks while holding an in-memory lock.

### Deadlock

```text
Thread A holds lock 1 and waits for lock 2
Thread B holds lock 2 and waits for lock 1
```

Prevent deadlocks through:

- A global lock-acquisition order.
- Fewer simultaneously held locks.
- Small lock scope.
- Timed or interruptible acquisition where appropriate.
- Avoiding calls into unknown code while locked.
- Combining state under one lock when practical.

### Starvation

An unfair scheduling policy or stream of competing work can indefinitely delay a particular contender. A fairness option can reduce some forms of starvation but may reduce throughput and cannot solve every higher-level starvation problem.

## Database optimistic locking

Database optimistic locking normally uses a version column.

```java
@Entity
class Product {
    @Id
    private Long id;

    @Version
    private long version;

    private int availableStock;

    void reserve(int quantity) {
        if (availableStock < quantity) {
            throw new IllegalStateException("Insufficient stock");
        }

        availableStock -= quantity;
    }
}
```

The persistence provider manages the `@Version` field. Application code may read it but must not directly modify it after the entity becomes persistent.

### Conceptual SQL

Two transactions both read:

```text
id = 10
available_stock = 8
version = 5
```

The provider conceptually performs an update similar to:

```sql
UPDATE product
SET available_stock = ?,
    version = 6
WHERE id = 10
  AND version = 5;
```

The first transaction updates one row and advances the version.

The second transaction's old expected version no longer matches:

```text
affected rows = 0
        ↓
optimistic conflict
        ↓
OptimisticLockException
```

The exact SQL is provider- and database-dependent, but the essential idea is a conditional update against the expected version.

### Lost update prevented

Without a version check:

```text
T1 reads stock 8
T2 reads stock 8
T1 writes stock 6
T2 writes stock 5

T1's update is silently lost
```

With optimistic versioning, T2 cannot successfully commit an update based on the stale version 5 after T1 has advanced it.

### Conflict detection may be delayed

Jakarta Persistence providers may defer SQL until flush or transaction commit. Therefore, `OptimisticLockException` may be thrown by:

- An entity operation.
- `EntityManager.flush()`.
- Transaction commit.

If the application needs to catch the conflict before commit processing leaves the current method, explicitly flushing can force pending writes:

```java
entityManager.flush();
```

An optimistic conflict marks the active transaction for rollback. Do not catch the exception and continue using the same failed transaction as though it were valid.

Retry in a new transaction after reloading fresh state.

## Jakarta Persistence optimistic lock modes

```java
Product product = entityManager.find(
        Product.class,
        productId,
        LockModeType.OPTIMISTIC
);
```

Relevant modes are:

| Mode | Meaning |
|---|---|
| `OPTIMISTIC` | Obtain optimistic guarantees for a versioned entity |
| `OPTIMISTIC_FORCE_INCREMENT` | Obtain optimistic guarantees and force a version increment |
| `READ` | Older synonym for `OPTIMISTIC`; prefer `OPTIMISTIC` |
| `WRITE` | Older synonym for `OPTIMISTIC_FORCE_INCREMENT`; prefer the explicit name |

Ordinary updates to a correctly versioned managed entity normally use its version automatically. Explicit optimistic lock modes are useful when a transaction needs version protection even without a normal state update, or when it intentionally forces a version advance.

An optimistic lock request for a non-versioned entity is not portably supported; the provider may throw `PersistenceException` when it cannot provide the requested semantics.

## Retrying a database optimistic conflict

```java
Product reserveWithRetry(long productId, int quantity) {
    for (int attempt = 1; attempt <= 3; attempt++) {
        try {
            return transactionTemplate.execute(status -> {
                Product product = repository.findById(productId)
                        .orElseThrow();

                product.reserve(quantity);
                entityManager.flush();
                return product;
            });
        } catch (OptimisticLockException conflict) {
            if (attempt == 3) {
                throw conflict;
            }

            backoff(attempt);
        }
    }

    throw new AssertionError("unreachable");
}
```

This is illustrative; the transaction framework determines where commit occurs and which translated exception type is exposed.

A safe retry requires:

1. Roll back the failed transaction.
2. Start a new transaction.
3. Reload current database state.
4. Re-evaluate the business rule.
5. Apply the new change.
6. Retry only within a bounded policy.

Do not merely repeat the same stale SQL or merge the same stale detached object without re-evaluating current state.

### Side effects and retries

This is dangerous inside a retryable transaction:

```java
paymentGateway.charge(command);
product.reserve(quantity);
```

If the database commit fails optimistically, retrying might charge the customer again.

Use patterns such as:

- Idempotency keys.
- Transactional outbox.
- Deduplication at the consumer.
- Compensating action where appropriate.
- Moving external effects after durable state transition while handling crash gaps explicitly.

Database rollback cannot automatically undo an already completed external API call.

## Detached entities and optimistic locking

A detached entity carries the version it had when loaded:

```text
detached Product version 5
database Product version 7
```

Merging or updating from the stale detached state can produce `OptimisticLockException`.

Do not treat the exception as a technical nuisance and overwrite the newer state blindly. The application must decide whether to:

- Reject the stale edit.
- Ask the user to reload.
- Merge non-conflicting fields.
- Re-run the business command against current state.
- Apply a domain-specific conflict-resolution rule.

The correct response depends on business semantics.

## Database pessimistic locking

Pessimistic locking obtains a database lock before the protected update:

```java
Product product = entityManager.find(
        Product.class,
        productId,
        LockModeType.PESSIMISTIC_WRITE
);

product.reserve(quantity);
```

Conceptually, a provider may use SQL such as:

```sql
SELECT id, available_stock, version
FROM product
WHERE id = ?
FOR UPDATE;
```

The exact SQL and lock behavior are database dialect, provider, transaction-isolation, and query dependent. Do not couple correctness to an assumed SQL translation without verifying the actual database behavior.

The lock is normally held until the database transaction commits or rolls back.

## Jakarta Persistence pessimistic lock modes

| Mode | Intended semantics |
|---|---|
| `PESSIMISTIC_READ` | Long-lived shared/read protection; other readers may proceed, conflicting writers are prevented |
| `PESSIMISTIC_WRITE` | Long-lived exclusive/write protection to serialize conflicting updates |
| `PESSIMISTIC_FORCE_INCREMENT` | Pessimistic write protection plus version increment |

Database support varies. A provider may need to use a stronger database lock to implement a requested read lock. Always test the generated SQL and behavior on the actual database.

Jakarta Persistence lock operations require an active transaction. Requesting a lock mode other than `NONE` without the required transaction results in `TransactionRequiredException`.

## Pessimistic database lock failures

When a pessimistic lock cannot be obtained:

- `PessimisticLockException` indicates a locking failure that causes transaction-level rollback.
- `LockTimeoutException` indicates a locking failure where only the statement is rolled back and the transaction is not automatically marked for rollback by that failure.

The application still needs an explicit policy:

- Retry in a new transaction.
- Return a conflict or busy response.
- Use a bounded timeout.
- Queue the command.
- Fail fast when waiting is undesirable.

Lock timeout hints are not uniformly portable. Jakarta Persistence explicitly warns that a database/provider may not observe the standard timeout hint in every situation.

## Pessimistic locking does not mean “lock everything”

A row lock protects the rows and lock scope actually selected by the database.

It may not automatically protect:

- A row that does not yet exist.
- Every row matching a changing predicate.
- Related entities or join-table rows.
- A business invariant spanning several rows.
- Data in another database.
- An external service or cache.
- Code that updates the same data outside the expected transaction protocol.

Phantom rows, gap locking, predicate locking, and relationship lock scope depend on the database, isolation level, query, index access path, and provider configuration.

Correctness requires locking the complete data set involved in the invariant or choosing a database constraint/isolation level that enforces it.

## Transaction isolation is not the same as lock strategy

Transaction isolation defines which anomalies concurrent transactions may observe. Optimistic or pessimistic locking is an application/provider strategy used within that isolation environment.

Examples:

- A version column can prevent a lost update for one entity but not necessarily prevent write skew across two different rows.
- A pessimistic lock on one product row does not protect a global inventory invariant involving several warehouses.
- Snapshot/MVCC reads may avoid blocking writers while version checks still detect conflicting updates at commit.
- Serializable isolation may reject or serialize transactions even when application-level optimistic locking is also present.

Treat these as related layers, not synonyms:

```text
database constraints
transaction isolation
database lock behavior
entity versioning
application retry policy
```

All may contribute to correctness.

## MVCC is not identical to optimistic locking

Multi-version concurrency control allows readers to observe a database snapshot while other transactions update newer versions.

An MVCC database may still:

- Acquire locks for writes.
- Detect serialization failures.
- Use version/timestamp metadata internally.
- Require an application `@Version` column to detect detached stale updates.

MVCC describes database concurrency internals and isolation behavior. Application optimistic locking describes validating that a particular state has not changed before accepting an update.

## HTTP conditional requests use the same optimistic idea

The pattern also appears outside Java memory and databases:

```http
GET /products/10
ETag: "version-5"
```

```http
PUT /products/10
If-Match: "version-5"
```

If the resource now has another version, the server rejects the stale update, commonly with HTTP `412 Precondition Failed`.

This is optimistic validation across a network boundary.

## Choosing optimistic locking

Optimistic locking is usually suitable when:

- Conflicts are genuinely rare.
- Reads greatly outnumber writes.
- Operations are short or cheap to recompute.
- Callers can tolerate conflict responses.
- Retry logic is bounded and safe.
- Work is deterministic or side-effect-free until commit.
- Holding database locks across user think-time would be unacceptable.
- The system is distributed and cannot share one process lock.

Examples:

- Editing a mostly read-only entity using `@Version`.
- Updating immutable in-memory state through CAS.
- Short optimistic reads with `StampedLock`.
- HTTP updates protected by an ETag.
- Low-contention counters or state machines.

## Choosing pessimistic locking

Pessimistic locking is usually suitable when:

- Conflicts are frequent.
- Retried work is expensive.
- The protected operation has non-repeatable side effects.
- A small hot data set is updated concurrently.
- The business rule requires reading and updating several values atomically.
- A conflict discovered only at commit would be too late or too wasteful.
- The lock can be held for a short, predictable time.

Examples:

- Reserving the last unit of a highly contended inventory item.
- Modifying a complex in-memory invariant under one lock.
- Serializing updates to one database row during a short transaction.
- Coordinating a resource whose operation cannot safely be replayed.

Pessimistic locking is not automatically correct for long transactions. Holding database locks while waiting for network calls or user input can destroy throughput and increase deadlock probability.

## Hybrid and adaptive strategies

The two approaches can be combined:

```text
try optimistic update
        ↓
few conflicts? keep retrying optimistically
        ↓
repeated conflicts? back off, queue, or acquire a lock
```

Examples:

- `StampedLock` tries an optimistic read, then falls back to a real read lock.
- An application tries a small number of version-based updates, then serializes work for a hot key.
- A CAS algorithm uses backoff or striped state under contention.
- A database workflow normally uses `@Version` but explicitly requests `PESSIMISTIC_WRITE` for a known hot operation.

Adaptive behavior requires measurements. Switching mechanisms can introduce new ordering and fairness complexity.

## Common mistakes

### Retrying forever

```java
while (true) {
    tryAgain();
}
```

Unbounded retries can consume CPU, amplify database load, and prevent useful work. Use a retry budget, backoff, observability, and a final failure policy.

### Repeating side effects inside an optimistic retry

An update function or transaction can execute more than once. Side effects need idempotency or transactional coordination.

### Treating every optimistic conflict as an infrastructure error

A conflict may be normal domain behavior: another user edited the same record first. It may deserve an HTTP conflict response or merge workflow, not an opaque retry loop.

### Holding a pessimistic lock during remote I/O

Network latency extends lock duration and increases blocking, timeout, and deadlock risk.

### Assuming `SELECT FOR UPDATE` locks an absent row

The behavior depends on database isolation, indexes, and gap/predicate-lock support. Enforce uniqueness and other invariants with database constraints.

### Forgetting the second layer of thread safety

A database lock coordinates database transactions. It does not make an in-memory Java object safe when several threads mutate that object outside the persistence protocol.

### Using a local Java lock in a distributed deployment

```java
synchronized (lock) {
    updateDatabase();
}
```

This coordinates only threads in one JVM. Another application instance has a different lock. Use database constraints/transactions, a distributed coordination mechanism, or architecture that assigns one owner.

### Assuming a pessimistic lock eliminates deadlocks

Pessimistic locking can create deadlocks. Consistent acquisition order and short transactions remain necessary.

### Manually editing the JPA version field

The persistence provider owns the version value. Direct application modification can break conflict detection.

### Continuing a transaction after optimistic failure

`OptimisticLockException` marks the current transaction for rollback. Retry in a fresh transaction and reload state.

## Practical decision checklist

```text
How often do real conflicts occur?
How expensive is discarded work?
Can the operation be safely retried?
Does it perform external side effects?
How long would a lock be held?
Can waiting threads/transactions time out?
Could multiple locks create a deadlock?
Does the invariant span multiple fields, rows, or systems?
Is the deployment distributed across JVMs?
Which database isolation and lock behavior are actually in use?
Do metrics show retry storms, lock waits, or deadlocks?
```

## Interview summary

> Optimistic locking assumes conflicts are rare: a participant reads a state or version, performs work, and commits only if the expected state is still current. CAS, `StampedLock` optimistic reads, JPA `@Version`, and HTTP ETags follow this model. Conflicts cause failed CAS, retry, merge, or abort, so retryable work must be bounded and side-effect-safe. Pessimistic locking acquires a monitor, `Lock`, or database lock before protected work, preventing conflicting participants from proceeding but introducing blocking, timeouts, lock convoys, starvation, and deadlocks. Choose optimistic control for low contention and cheap retries; choose pessimistic control when contention is high, retries are expensive, or operations cannot safely be repeated. Transaction isolation, database constraints, lock scope, and application retry policy remain separate parts of the correctness design.

## Official references

- [Java SE 26 `AtomicReference` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/atomic/AtomicReference.html)
- [Java SE 26 `AtomicStampedReference` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/atomic/AtomicStampedReference.html)
- [Java SE 26 `StampedLock` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/locks/StampedLock.html)
- [Java SE 26 `ReentrantLock` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/locks/ReentrantLock.html)
- [Jakarta Persistence 3.2 — Entity Versions and Optimistic Locking](https://jakarta.ee/specifications/persistence/3.2/jakarta-persistence-spec-3.2#entity-versions)
- [Jakarta Persistence 3.2 `LockModeType`](https://jakarta.ee/specifications/persistence/3.2/apidocs/jakarta.persistence/jakarta/persistence/lockmodetype)
- [Jakarta Persistence 3.2 `OptimisticLockException`](https://jakarta.ee/specifications/persistence/3.2/apidocs/jakarta.persistence/jakarta/persistence/optimisticlockexception)
- [Jakarta Persistence 3.2 `EntityManager`](https://jakarta.ee/specifications/persistence/3.2/apidocs/jakarta.persistence/jakarta/persistence/entitymanager)
