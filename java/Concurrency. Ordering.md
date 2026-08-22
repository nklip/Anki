# Ordering

## Front

What does **ordering** mean in Java concurrency?

## Back

Ordering describes the sequence in which memory operations are observed.

The compiler, JIT compiler, and CPU may reorder operations when the reordering does not change the result of a single-threaded program. Another thread, however, may observe those operations in an unexpected order when no happens-before relationship exists.

### Ordering problem

```java
int data = 0;
boolean ready = false;
```

**Thread A**

```java
data = 42;
ready = true;
```

**Thread B**

```java
if (ready) {
    System.out.println(data);
}
```

Without synchronization, Thread B is not guaranteed to observe the writes in the intended order. It may observe `ready == true` without reliably observing `data == 42`.

### Ordering solution

```java
int data = 0;
volatile boolean ready = false;
```

When Thread B reads `ready == true`, the write to `data` that occurred before the volatile write is also visible:

```java
// Thread A
data = 42;
ready = true;

// Thread B
if (ready) {
    System.out.println(data); // 42
}
```

The same ordering guarantee can be created with `synchronized`, locks, and other happens-before relationships.

### Key idea

**Ordering controls which sequence of memory operations another thread is allowed to observe.**
