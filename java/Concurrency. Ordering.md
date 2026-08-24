# Concurrency. Ordering

## Front

What does ordering mean in Java concurrency, and how does *happens-before* make cross-thread observations predictable?

## Back

**Ordering means constraints on which actions must be observable before other actions; it does not mean that all threads share one global timeline.**

The Java Memory Model uses three related ideas:

- **Program order:** each thread must behave as if its actions follow that thread's source-level semantics. The compiler or CPU may still rearrange work when the difference cannot be observed legally.
- **Synchronization order:** one total order over synchronization actions, such as volatile accesses and monitor lock/unlock actions.
- **Happens-before:** a partial order built from program order, cross-thread *synchronizes-with* edges, and transitivity. If action A happens-before B, A's effects are visible to and ordered before B.

The diagram shows how one volatile flag safely publishes earlier ordinary writes:

![Program-order and volatile edges forming a happens-before chain](svg/concurrency-volatile-happens-before.svg)

```java
final class Publication {
    private int data;
    private volatile boolean ready;

    void publish() {       // Thread A
        data = 42;
        ready = true;      // volatile write (release)
    }

    void consume() {       // Thread B
        if (ready) {       // subsequent volatile read (acquire)
            System.out.println(data); // guaranteed to print 42
        }
    }
}
```

The chain is: `data = 42` → **program order** → volatile write of `ready` → **synchronizes-with** → subsequent volatile read of `ready` → **program order** → read of `data == 42`.

Without `volatile` or another synchronization edge, the conflicting ordinary accesses form a **data race**. Thread B is then not guaranteed to observe the two writes as intended.

Other common happens-before edges include:

- leaving a `synchronized` block → later entering one guarded by the same monitor;
- `thread.start()` → actions in the started thread;
- all actions in a thread → another thread successfully returning from `join()`.

Ordering can provide visibility, but it does not make a compound action atomic: `volatile count++` can still lose updates.

## Sources

- [Java Language Specification §17.4 — Memory Model](https://docs.oracle.com/javase/specs/jls/se25/html/jls-17.html#jls-17.4)
- [`java.util.concurrent` memory-consistency properties](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/package-summary.html#MemoryVisibility)
