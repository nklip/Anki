# Double-Checked Locking in Modern Java

## Front

What is the **double-checked locking** pattern in Java?

Why was its historical implementation broken, how does the correct modern version use `volatile`, why are two null checks required, and which alternatives are usually preferable?

## Back

**Double-checked locking (DCL)** lazily initializes a shared object while avoiding synchronization after initialization has completed.

The correct modern Java form is:

```java
final class ServiceProvider {
    private static volatile Service instance;

    private ServiceProvider() {}

    static Service instance() {
        Service result = instance; // volatile read

        if (result == null) {       // first check: fast path
            synchronized (ServiceProvider.class) {
                result = instance;  // second volatile read

                if (result == null) { // second check: initialization path
                    result = new Service();
                    instance = result; // volatile write: publish
                }
            }
        }

        return result;
    }
}
```

The essential requirements are:

```text
volatile reference
        +
stable shared lock
        +
check outside the lock
        +
check again inside the lock
        +
fully construct before publishing
```

Since the Java 5 memory-model revision, this pattern is correct when implemented carefully with a volatile field.

## What problem does DCL solve?

A simple synchronized lazy accessor is correct:

```java
final class ServiceProvider {
    private static Service instance;

    static synchronized Service instance() {
        if (instance == null) {
            instance = new Service();
        }

        return instance;
    }
}
```

However, every call acquires the class monitor, including calls made long after initialization.

DCL moves the common initialized path outside the synchronized block:

```text
instance already exists?
        │
        ├─ yes → return after a volatile read; no lock
        │
        └─ no  → acquire the lock and initialize if still necessary
```

The optimization matters only when:

- Initialization must be lazy.
- The accessor is called frequently.
- Avoiding the post-initialization lock is measurably useful.
- A simpler mechanism does not fit.

Modern JVMs optimize uncontended synchronization well. DCL should not be introduced automatically merely because a value is lazy.

## The historically broken implementation

This version is incorrect:

```java
final class BrokenProvider {
    private static Service instance; // not volatile

    static Service instance() {
        if (instance == null) {
            synchronized (BrokenProvider.class) {
                if (instance == null) {
                    instance = new Service();
                }
            }
        }

        return instance;
    }
}
```

The outer read is not synchronized and the field is not volatile. One thread writes `instance` while another thread reads it without a happens-before relationship. This is a **data race**.

The reader on the fast path does not acquire the monitor, so it does not receive the visibility guarantee created by the writer's monitor release.

### Unsafe publication

Conceptually, creating and publishing the object involves:

```text
allocate memory
initialize object state in the constructor
publish the reference into instance
```

Without safe publication, another thread may observe the non-null reference without being guaranteed to observe all constructor writes correctly. Fields may appear to retain default or stale values.

The problem should be described in Java Memory Model terms:

```text
constructor writes
        ✕ no happens-before path
unsynchronized reader
```

It is common to illustrate the bug as publication appearing before initialization. That is useful intuition, but the fundamental issue is not a required literal source-code reordering. The fundamental issue is the data race and the absence of a visibility/order guarantee.

## Why `volatile` fixes publication

```java
private static volatile Service instance;
```

The Java Memory Model guarantees:

> A write to a volatile field happens-before every subsequent read of that same field.

The successful initialization path is:

```java
result = new Service(); // constructor completes
instance = result;      // volatile write: release
```

The initialized fast path starts with:

```java
Service result = instance; // volatile read: acquire
```

The complete happens-before chain is:

```text
writes performed by Service construction
        │
        │ program order
        ▼
volatile write: instance = result
        │
        │ synchronizes-with
        ▼
volatile read: result = instance
        │
        │ program order
        ▼
reader uses result
```

By transitivity, the thread that reads the published reference is guaranteed to see state written before the volatile publication.

The volatile field provides both:

- **Visibility** of the reference and prior construction effects.
- **Ordering** sufficient for safe publication.

It does not lock other threads or make later mutable operations inside `Service` thread-safe.

## Why the first check exists

```java
if (result == null) {
    synchronized (ServiceProvider.class) {
        // initialization path
    }
}
```

The first check is the optimization.

After initialization, calls perform approximately:

```text
volatile read → non-null → return
```

They do not acquire the initialization monitor.

Without the first check, the code becomes ordinary synchronized lazy initialization rather than double-checked locking.

## Why the second check exists

The first check occurs before acquiring the lock. Several threads can observe null before any one of them initializes the object.

Suppose Thread A and Thread B execute:

```text
Thread A                       Thread B
--------                       --------
reads null                     reads null
acquires lock                  waits for lock
creates Service
publishes instance
releases lock
                               acquires lock
                               must check again
```

If Thread B does not check again, it creates a second `Service` even though Thread A already initialized the field.

Correct code:

```java
synchronized (ServiceProvider.class) {
    result = instance;

    if (result == null) {
        result = new Service();
        instance = result;
    }
}
```

The second check is the correctness check that prevents queued threads from repeating initialization.

## Why the local variable is used

```java
Service result = instance;
```

The local variable:

- Gives the method a stable value to return.
- Avoids unnecessary repeated volatile reads on the initialized path.
- Makes the volatile acquisition point explicit.
- Prevents a concurrently reset field from producing inconsistent repeated reads, although resettable DCL is usually a bad design.

A shorter correct form exists:

```java
static Service instance() {
    if (instance == null) {
        synchronized (ServiceProvider.class) {
            if (instance == null) {
                instance = new Service();
            }
        }
    }

    return instance;
}
```

It still requires `instance` to be volatile. The local-variable form is the conventional optimized version because it reduces volatile reads and keeps one acquired reference for the return.

## Volatile alone is not sufficient for single initialization

This is safely visible but not atomically initialized:

```java
private static volatile Service instance;

static Service instance() {
    if (instance == null) {
        instance = new Service();
    }

    return instance;
}
```

Two threads can both observe null and both construct a service:

```text
Thread A reads null
Thread B reads null
Thread A constructs and writes Service A
Thread B constructs and writes Service B
```

The volatile writes are visible and individually atomic, but the complete check-then-act operation is not atomic.

The synchronized block is still necessary when exactly one successful initialization must occur.

## Locking alone is insufficient for the unsynchronized fast path

The broken DCL form does use a synchronized block during initialization, but readers that observe non-null outside that block do not acquire the same monitor.

Monitor semantics guarantee:

```text
unlock of monitor M
        happens-before
subsequent lock of the same monitor M
```

They do not automatically publish to a thread that skips the lock and performs an ordinary field read.

The volatile reference connects the initialization effects to the lock-free fast path.

## Use a stable lock

The locking object must remain the same for every initializer:

```java
synchronized (ServiceProvider.class) {
}
```

For an instance-level lazy field:

```java
final class Component {
    private volatile Helper helper;

    Helper helper() {
        Helper result = helper;

        if (result == null) {
            synchronized (this) {
                result = helper;

                if (result == null) {
                    result = new Helper();
                    helper = result;
                }
            }
        }

        return result;
    }
}
```

This is correct only if the `Component` object itself is also safely published.

Do not synchronize on:

- A field that can be reassigned.
- A boxed primitive.
- A string literal.
- A publicly accessible object that unrelated code may lock.

Prefer a private stable lock when locking on `this` or the class object would expose unwanted contention:

```java
private final Object initializationLock = new Object();
```

## Construction must finish before publication

Correct order:

```java
Service created = new Service();
instance = created;
```

Do not publish `this` from the constructor:

```java
final class Service {
    Service() {
        Registry.register(this); // premature escape
    }
}
```

The volatile assignment in `ServiceProvider` cannot undo a separate premature publication that occurred during construction.

Avoid starting threads, registering callbacks, or exposing `this` from constructors unless the design provides another complete synchronization protocol.

## Safe publication does not make the service immutable

```java
final class Service {
    private int requestCount;

    void recordRequest() {
        requestCount++; // still not thread-safe
    }
}
```

DCL safely publishes the initial state. Every later mutable operation still needs its own thread-safety design:

- Immutable state.
- Internal synchronization.
- Atomic fields.
- Thread confinement.
- Concurrent collections.

The singleton accessor being thread-safe does not imply that the returned singleton is thread-safe.

## `final` fields do not replace volatile publication

The Java Memory Model gives correctly constructed final fields special visibility guarantees, but this does not make broken DCL correct.

Without a volatile reference or another safe-publication mechanism:

- The reference field still has a data race.
- Non-final fields are not safely published.
- The complete object invariant may not be visible.
- Later mutations remain unsynchronized.

Use the correct publication mechanism even when the constructed class is mostly or entirely final.

## What if initialization throws?

```java
result = new Service();
instance = result;
```

If construction throws before the volatile assignment:

- `instance` remains null.
- The exception propagates to the caller.
- A later call can attempt initialization again.

This retry behavior may or may not be desirable.

Constructor or factory side effects can occur more than once across failed attempts:

```text
open external connection
write external record
register callback
constructor later throws
```

Initialization code should either be free of irreversible partial side effects or include explicit cleanup and failure policy.

## Null cannot represent both “uninitialized” and a valid result

DCL normally uses null as the sentinel:

```text
null     = not initialized
non-null = initialized
```

If the initializer may validly return null, the field cannot distinguish:

- Not initialized yet.
- Initialized successfully with a null result.

Use an explicit state object, sentinel instance, `Optional`, future, or another initialization abstraction when null is a valid computed value.

## Avoid resettable double-checked locking

DCL is easiest to reason about as a one-way transition:

```text
null → one safely published non-null instance
```

Adding reset or replacement creates lifecycle questions:

```java
static void reset() {
    instance = null;
}
```

Another thread may still be using the old service while a new one is created. Closing the old resource can race with current users.

Use an explicit lifecycle manager, immutable versioned snapshots, reference counting, locking around the lifecycle, or dependency-injection scope rather than casually resetting a DCL singleton.

## Initialization-on-demand holder idiom

For a static lazy singleton, this is usually simpler:

```java
final class ServiceProvider {
    private ServiceProvider() {}

    private static final class Holder {
        private static final Service INSTANCE = new Service();
    }

    static Service instance() {
        return Holder.INSTANCE;
    }
}
```

The nested `Holder` class is initialized when it is first actively used. JVM class-initialization rules provide synchronization and safe publication.

Advantages:

- Lazy initialization.
- No explicit volatile field.
- No handwritten locking.
- No volatile read on each initialized access.
- Small and easy to review.

Important failure difference:

- DCL normally retries after a constructor exception because the field remains null.
- Failed class initialization normally results in `ExceptionInInitializerError`; later active use observes that the class could not be initialized, commonly through `NoClassDefFoundError`, rather than retrying construction.

Choose the failure behavior intentionally.

## Eager static initialization

When laziness is unnecessary:

```java
final class ServiceProvider {
    private static final Service INSTANCE = new Service();

    static Service instance() {
        return INSTANCE;
    }
}
```

This is initialized when `ServiceProvider` is initialized, not necessarily when the JVM process starts.

It is usually the clearest option when construction is cheap and failure during class initialization is acceptable.

## Enum singleton

```java
enum ServiceSingleton {
    INSTANCE;

    private final Service service = new Service();

    Service service() {
        return service;
    }
}
```

Enum initialization is thread-safe and enum serialization preserves the enum-constant identity. It is useful when an enum-shaped globally accessible singleton is appropriate.

It is less suitable when:

- The singleton must extend another class.
- Creation requires runtime arguments.
- Dependency injection should control the lifecycle.
- Retryable lazy failure behavior is required.

## Always-synchronized accessor

```java
private static Service instance;

static synchronized Service instance() {
    if (instance == null) {
        instance = new Service();
    }

    return instance;
}
```

This is simple, correct, and often fast enough. Prefer it over DCL unless the post-initialization synchronization is a measured concern.

## Dependency injection

In an application framework, let the dependency-injection container construct and scope the service:

```java
final class Controller {
    private final Service service;

    Controller(Service service) {
        this.service = service;
    }
}
```

Advantages include:

- Explicit dependencies.
- Easier testing.
- Configurable scopes.
- Centralized lifecycle and cleanup.
- No global service locator.

DCL solves thread-safe lazy publication; it does not solve architectural dependency management.

## Per-key lazy initialization

Do not implement one DCL field for every key. Use a concurrent map when the requirement is memoization or per-key initialization:

```java
private final ConcurrentHashMap<String, Service> services =
        new ConcurrentHashMap<>();

Service serviceFor(String tenant) {
    return services.computeIfAbsent(
            tenant,
            this::createService
    );
}
```

`ConcurrentHashMap.computeIfAbsent()` atomically establishes a mapping when absent. Keep the mapping function short and avoid recursively modifying the same map from it.

If entries can be removed, a value may be recomputed after removal. “Once per current mapping” is not the same as “once for the lifetime of the process.”

## AtomicReference alternative and its trap

A CAS can atomically select one published instance:

```java
private static final AtomicReference<Service> INSTANCE =
        new AtomicReference<>();

static Service instance() {
    Service result = INSTANCE.get();

    if (result != null) {
        return result;
    }

    Service created = new Service();

    if (INSTANCE.compareAndSet(null, created)) {
        return created;
    }

    return INSTANCE.get();
}
```

This can construct several candidate services concurrently; only one wins publication. Losing candidates are discarded.

That is unacceptable when construction:

- Is expensive.
- Has side effects.
- Acquires resources requiring cleanup.
- Must happen exactly once.

CAS provides atomic publication, not automatically exactly-once construction. Use locking or a future-based initialization abstraction when duplicate construction is not acceptable.

## Singleton scope is per class loader

A static field belongs to a class as defined by a particular class loader.

If the same class is loaded by different class loaders, each loaded class can have its own static `instance`:

```text
ClassLoader A → ServiceProvider class A → instance A
ClassLoader B → ServiceProvider class B → instance B
```

DCL guarantees one published instance through that accessor within that class-loading scope. It does not guarantee one object across every class loader, process, machine, or service instance.

Reflection, cloning, custom serialization, or direct constructor access may also create additional objects unless the type is designed to prevent or control them.

## Virtual threads do not change DCL semantics

Platform threads and virtual threads follow the same Java Memory Model.

The requirements remain:

- Volatile publication.
- Correct locking.
- Both checks.
- No premature escape.
- A thread-safe returned object when shared.

Virtual threads do not make a racy non-volatile DCL implementation correct.

## Choosing an initialization technique

| Technique | Lazy? | Fast initialized path | Retry after failure? | Complexity | Typical choice |
|---|---:|---:|---:|---:|---|
| `static final` field | At provider class initialization | Yes | No normal retry | Very low | Default when extra laziness is unnecessary |
| Initialization-on-demand holder | Yes | Yes | Normally no | Low | Preferred static lazy singleton |
| `enum` singleton | At enum initialization | Yes | Normally no | Low | Serialization-safe enum-shaped singleton |
| Synchronized accessor | Yes | Acquires monitor | Yes if field remains null | Low | Prefer when performance is adequate |
| Correct DCL | Yes | Volatile read; no lock | Yes if publication never occurs | Medium/high | Specialized hot lazy accessor |
| Naive `AtomicReference` CAS | Yes | Atomic read | Yes | Medium | Only if duplicate construction is acceptable |
| Dependency injection | Container-defined | Container-defined | Container-defined | Architectural | Preferred in managed applications |

“Retry after failure” depends on where the exception occurs and whether the implementation records a permanent failure state.

## Common mistakes

### Missing `volatile`

```java
private static Service instance; // broken DCL
```

The lock-free read races with publication and does not safely acquire constructor effects.

### Missing the inner check

```java
if (instance == null) {
    synchronized (LOCK) {
        instance = new Service(); // several waiting threads may repeat this
    }
}
```

Every thread that observed null before waiting can construct another object.

### Missing the outer check

```java
synchronized (LOCK) {
    if (instance == null) {
        instance = new Service();
    }
}
```

This is correct ordinary synchronized lazy initialization, but it is no longer double-checked locking and every call acquires the lock.

### Using different locks

```java
synchronized (new Object()) {
    // Every call locks a different object: no mutual exclusion.
}
```

All initialization attempts must coordinate through the same stable monitor.

### Publishing before construction finishes

```java
this escapes to another component during construction;
```

Later volatile assignment cannot repair an earlier unsafe escape.

### Assuming the singleton is automatically thread-safe

Safe construction and publication do not protect future mutations.

### Resetting the field without a lifecycle protocol

Readers can retain and use the old instance while another thread replaces or closes it.

### Using DCL when class initialization already solves the problem

The holder idiom or a static final field is normally shorter and harder to get wrong.

## Interview explanation

A strong short explanation is:

> The first check avoids locking after initialization. The synchronized block allows only one initializer at a time. The second check prevents threads that previously observed null and then waited for the lock from constructing another instance. The field must be volatile because the fast-path reader does not acquire the initialization monitor: the volatile write safely publishes constructor effects, and the later volatile read acquires them. Without volatile, the outer read races with publication and may observe an incompletely published object. For a static lazy singleton, the initialization-on-demand holder is usually simpler.

## Key review checklist

```text
Is the shared reference volatile?
Is the lock stable and shared by every initializer?
Is there a check before locking?
Is there another check after locking?
Does construction finish before volatile publication?
Can the constructor leak this?
Is a null result possible?
Can initialization fail, and should it retry?
Is reset/replacement supported safely?
Is the returned object's later mutable state thread-safe?
Would a holder, static field, synchronized accessor, or DI be simpler?
```

## Official references

- [JLS §17.4.5 — Happens-before Order](https://docs.oracle.com/javase/specs/jls/se26/html/jls-17.html#jls-17.4.5)
- [JLS §8.3.1.4 — Volatile Fields](https://docs.oracle.com/javase/specs/jls/se26/html/jls-8.html#jls-8.3.1.4)
- [JLS §12.4 — Initialization of Classes and Interfaces](https://docs.oracle.com/javase/specs/jls/se26/html/jls-12.html#jls-12.4)
- [JLS §12.4.2 — Detailed Initialization Procedure](https://docs.oracle.com/javase/specs/jls/se26/html/jls-12.html#jls-12.4.2)
- [Java SE 26 `ConcurrentHashMap.computeIfAbsent()`](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/ConcurrentHashMap.html#computeIfAbsent(K,java.util.function.Function))
- [Java SE 26 `AtomicReference` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/atomic/AtomicReference.html)
