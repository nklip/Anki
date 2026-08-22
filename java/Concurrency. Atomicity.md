# Atomicity

## Front

What does **atomicity** mean in Java concurrency?

## Back

An operation is **atomic** when it happens as one indivisible action.

Other threads cannot observe it halfway through: they see either the state before the operation or the state after it.

### Non-atomic example

```java
count++;
```

Although this is one Java statement, it consists of several actions:

1. Read `count`.
2. Add `1`.
3. Write the new value.

Two threads can read the same old value and overwrite each other's updates. This is a **lost update**.

### Atomic solution

```java
AtomicInteger count = new AtomicInteger();

count.incrementAndGet();
```

Another solution is to protect the compound operation with the same lock:

```java
synchronized (lock) {
    count++;
}
```

> **Important:** `volatile` guarantees visibility and ordering, but it does **not** make compound operations such as `count++` atomic.

### Key idea

**Atomicity prevents other threads from observing or interfering with a partially completed operation.**
