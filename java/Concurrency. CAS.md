# Compare-And-Set (CAS) in Java

## Front

What is **Compare-And-Set (CAS)** in Java, how does a CAS retry loop work, what memory guarantees does it provide, and what are its main limitations?

## Back

**Compare-And-Set (CAS)** is an atomic conditional update:

```text
CAS(memory, expected, update):
    if memory == expected:
        memory = update
        return true
    else:
        return false
```

The comparison and possible write happen as one indivisible operation. No other thread can change that value between the comparison and the write performed by the CAS operation.

CAS is also called **Compare-And-Swap**. Java APIs normally use the name `compareAndSet`.

### Basic Java example

```java
AtomicInteger value = new AtomicInteger(10);

boolean updated = value.compareAndSet(10, 11);

System.out.println(updated);   // true
System.out.println(value.get()); // 11
```

The update succeeds only if the current value is still `10` when the atomic comparison occurs.

```java
boolean updatedAgain = value.compareAndSet(10, 12);

System.out.println(updatedAgain); // false
System.out.println(value.get());  // still 11
```

A failed CAS does not modify the value.

### Why CAS prevents a lost update

Suppose two threads try to increment a value currently equal to `10`:

```text
Thread A reads 10 and calculates 11
Thread B reads 10 and calculates 11

Thread A: CAS(10, 11) → succeeds
Thread B: CAS(10, 11) → fails because the value is now 11
Thread B retries using the new value
```

Without CAS, both threads could write `11`, losing one increment. CAS detects that Thread B's observation became stale.

### The CAS retry-loop pattern

```java
AtomicInteger balance = new AtomicInteger(100);

void withdraw(int amount) {
    int current;
    int next;

    do {
        current = balance.get();

        if (current < amount) {
            throw new IllegalStateException("Insufficient funds");
        }

        next = current - amount;
    } while (!balance.compareAndSet(current, next));
}
```

The loop performs three conceptual steps:

1. Read the current value.
2. Calculate a new value from that observation.
3. Publish it only if the observed value is still current.

If another thread wins the race, `compareAndSet()` returns `false`, so the losing thread reads the latest state, recalculates, and retries.

This is an **optimistic** strategy: proceed assuming no conflict, then detect and recover from a conflict.

### Prefer higher-level atomic methods when they express the operation

Manual loop:

```java
int current;
int next;

do {
    current = counter.get();
    next = current + 1;
} while (!counter.compareAndSet(current, next));
```

Prefer:

```java
counter.incrementAndGet();
```

For a custom transformation:

```java
int updated = counter.updateAndGet(current -> current * 2);
```

The function passed to `updateAndGet()`, `getAndUpdate()`, `accumulateAndGet()`, or `getAndAccumulate()` must be **side-effect-free**, because contention may cause Java to apply it more than once.

Bad:

```java
counter.updateAndGet(current -> {
    sendNotification(); // may execute multiple times
    return current + 1;
});
```

Calculate the atomic state first, then perform non-idempotent effects separately with an appropriate coordination design.

### Atomic classes that expose CAS-style operations

- `AtomicBoolean`
- `AtomicInteger`
- `AtomicLong`
- `AtomicReference<V>`
- Atomic arrays such as `AtomicIntegerArray`
- `AtomicStampedReference<V>` and `AtomicMarkableReference<V>`
- `VarHandle` for atomic access to fields, array elements, and other variables

For `AtomicReference`, comparison uses reference identity, equivalent to `==`, not `equals()`:

```java
AtomicReference<String> ref =
        new AtomicReference<>(new String("A"));

String equalButDifferent = new String("A");

ref.compareAndSet(equalButDifferent, "B"); // false
```

The expected argument must be the same object reference currently stored in `ref`.

### Updating several related fields

CAS directly updates one atomic variable. To preserve an invariant spanning several fields, place them in one immutable state object and CAS the reference:

```java
record AccountState(long balance, long version) {}

final class Account {
    private final AtomicReference<AccountState> state =
            new AtomicReference<>(new AccountState(100, 0));

    void deposit(long amount) {
        state.updateAndGet(oldState ->
                new AccountState(
                        oldState.balance() + amount,
                        oldState.version() + 1
                )
        );
    }
}
```

Publishing the new reference makes the complete immutable state transition atomic.

Separate atomics do **not** make a multi-variable invariant atomic:

```java
AtomicInteger debit = new AtomicInteger();
AtomicInteger credit = new AtomicInteger();

debit.incrementAndGet();
credit.incrementAndGet();
```

Another thread may observe the state between the two operations. Use one immutable aggregate or a lock when the transition must be indivisible.

### Memory-ordering guarantee

Standard `compareAndSet()` has volatile read-and-write memory effects:

- It reads the current value with volatile-read semantics.
- On success, it writes the new value with volatile-write semantics.
- The comparison and conditional update are atomic.

Therefore, a successful CAS can safely publish preceding writes, and a thread that subsequently observes that update with the corresponding volatile semantics sees the published state.

CAS is not only an atomicity mechanism; its standard Java form also provides visibility and ordering guarantees.

### `compareAndSet()` versus `compareAndExchange()`

```java
boolean success = value.compareAndSet(expected, update);
```

`compareAndSet()` returns only success or failure.

```java
int witness = value.compareAndExchange(expected, update);
```

`compareAndExchange()` returns the **witness value** that was observed:

- If `witness == expected`, the update succeeded.
- Otherwise, `witness` is the value that prevented the update.

This can be useful in algorithms that can reuse the observed value instead of performing a separate read after failure.

### Strong versus weak CAS

`compareAndSet()` is the ordinary strong operation. If it returns `false`, the observed value did not match the expected value.

The `weakCompareAndSet...()` variants may **fail spuriously**: they may return `false` even when the value matches. They are intended for retry loops and expose different memory-ordering strengths:

- `weakCompareAndSetPlain(...)`
- `weakCompareAndSetAcquire(...)`
- `weakCompareAndSetRelease(...)`
- `weakCompareAndSetVolatile(...)`

The unsuffixed `weakCompareAndSet(...)` method on atomic classes is deprecated because its name suggests volatile effects even though it has plain memory effects. Prefer an explicitly named variant.

Use the standard `compareAndSet()` unless lower-level code has a measured reason to select a weaker operation and its memory semantics are fully understood.

### The ABA problem

CAS checks only whether the current value equals the expected value at comparison time. It cannot detect that the value changed and later returned to the same value:

```text
Thread A reads A

Thread B changes A → B
Thread B changes B → A

Thread A executes CAS(A, C) → succeeds
```

Thread A cannot tell that the state temporarily became `B`. This is the **ABA problem**.

ABA matters when the intermediate changes carry meaning—for example, when nodes are removed and reused in a lock-free data structure.

One solution is to compare both the reference and a version stamp:

```java
AtomicStampedReference<Node> head =
        new AtomicStampedReference<>(initialNode, 0);

int[] stampHolder = new int[1];
Node expected = head.get(stampHolder);
int expectedStamp = stampHolder[0];

boolean changed = head.compareAndSet(
        expected,
        replacement,
        expectedStamp,
        expectedStamp + 1
);
```

The reference may return to the same object, but a changed stamp reveals that an intervening update occurred.

Related tools:

- `AtomicStampedReference<V>` pairs a reference with an integer version.
- `AtomicMarkableReference<V>` pairs a reference with a boolean mark, often used for logical deletion.

### CAS does not automatically make an algorithm lock-free

The CAS operation itself does not acquire a Java monitor or explicit lock. However, a complete algorithm must be analyzed separately.

Important progress terms:

- **Lock-free:** the system as a whole keeps making progress; an individual thread may starve.
- **Wait-free:** every operation completes within a bounded number of its own steps.
- **Obstruction-free:** a thread completes if it eventually runs without interference.

A CAS retry loop may repeatedly lose under contention, so it is not automatically wait-free or fair. The Java API guarantees atomic behavior, not that every CAS maps to one particular hardware instruction or that every algorithm using it has a specific progress guarantee.

### Advantages

- Avoids blocking and lock ownership for simple state transitions.
- Prevents lost updates on a single atomic variable.
- A failed attempt does not suspend the thread.
- Often performs well under low or moderate contention.
- Forms the basis of many concurrent data structures and atomic APIs.

### Limitations

- Repeated retries waste CPU under heavy contention.
- Competing writes can cause cache-line contention.
- Individual threads may starve; CAS is not fair.
- Complex retry logic is difficult to design and verify.
- ABA can make an unchanged-looking value misleading.
- One CAS cannot directly protect an invariant spread across independent variables.
- CAS provides no waiting or notification mechanism.

For a highly contended statistical counter, `LongAdder` may scale better than one `AtomicLong`, but it does not provide the same single-value CAS semantics or an atomic snapshot suitable for every use case.

Use a lock when the operation spans complex mutable state, requires fairness, must coordinate waiting threads, or is clearer and safer as a critical section.

### CAS versus related mechanisms

| Mechanism | What it provides |
|---|---|
| `volatile` | Visibility and ordering for reads/writes; does not make `count++` atomic |
| CAS / atomic class | Atomic conditional update of one variable plus defined memory effects |
| `synchronized` / `Lock` | Mutual exclusion across an arbitrary critical section and multiple fields |
| `LongAdder` | Scalable accumulation under contention; not a replacement for CAS-based state transitions |

### Common mistakes

1. Assuming `volatile int count; count++;` is atomic.
2. Calculating the update once outside the retry loop and reusing stale data.
3. Performing side effects inside an update function that may run repeatedly.
4. Assuming several atomic variables form one atomic transaction.
5. Ignoring ABA when a value can leave and return to the expected state.
6. Assuming non-blocking means wait-free, fair, or always faster than locking.
7. Using `AtomicReference.compareAndSet()` as though it compared objects with `equals()`.

### Interview summary

> CAS atomically changes a value only if it still equals an expected value. A failed CAS tells a retry loop that its observation became stale, preventing lost updates without mutual exclusion. Java exposes CAS through atomic classes and `VarHandle`; ordinary `compareAndSet()` has volatile memory effects. CAS works best for small state transitions but can suffer from retries, starvation, cache contention, and ABA, and it does not make multi-variable invariants atomic by itself.

### Official references

- [AtomicInteger API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/atomic/AtomicInteger.html)
- [java.util.concurrent.atomic package](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/atomic/package-summary.html)
- [VarHandle API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/lang/invoke/VarHandle.html)
- [AtomicStampedReference API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/atomic/AtomicStampedReference.html)
