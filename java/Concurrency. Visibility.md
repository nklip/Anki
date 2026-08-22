# Visibility

## Front

What does **visibility** mean in Java concurrency?

## Back

Visibility means that a value written by one thread becomes observable by another thread.

Without synchronization, the Java Memory Model does not guarantee when—or whether—another thread will observe a write.

### Visibility problem

```java
boolean ready = false;
```

**Thread A**

```java
ready = true;
```

**Thread B**

```java
while (!ready) {
}
```

Thread B is not guaranteed to observe `true`. The compiler, JVM, CPU, and CPU caches may reuse or reorder values when no happens-before relationship exists.

### Visibility solution

```java
volatile boolean ready = false;
```

A write to a `volatile` variable **happens-before** every subsequent read of that same variable.

Visibility can also be established by:

- Entering and leaving the same `synchronized` lock.
- Locking and unlocking the same `Lock`.
- Starting a thread with `Thread.start()`.
- Waiting for a thread with `Thread.join()`.
- Using concurrent classes such as `AtomicInteger`.

### Key idea

**Visibility determines whether one thread can observe another thread's latest writes.**
