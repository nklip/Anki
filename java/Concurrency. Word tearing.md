# Concurrency. Word Tearing

## Front

What is word tearing, and can it happen in Java?

## Back

**Word tearing** happens when multiple logical variables share one machine word and updating one variable accidentally changes another part of that word.

For example, a processor might update one byte by:

1. Reading the entire machine word.
2. Changing one byte inside it.
3. Writing the entire word back.

If two threads do this concurrently for different bytes, one whole-word write could overwrite the other thread's update.

## Java forbids word tearing between distinct variables

The Java Memory Model treats every field and every array element as distinct.

```java
byte[] values = new byte[2];

// Thread A
values[0] = 1;

// Thread B
values[1] = 2;
```

The write to `values[0]` must not overwrite or corrupt `values[1]`, even if both bytes occupy the same machine word.

The JVM must provide this guarantee even on hardware that cannot update a single byte directly.

## This does not make shared data automatically thread-safe

The guarantee only prevents one field or element from corrupting a different field or element.

Two threads modifying the **same** variable can still have:

- Lost updates.
- Visibility problems.
- Race conditions.
- Incorrect ordering.

```java
int counter = 0;

// Not atomic: read, add, write
counter++;
```

An `int` read or write is atomic, but `counter++` is a compound operation and is not atomic.

## Special rule for `long` and `double`

The Java Language Specification separately permits a non-`volatile` `long` or `double` read or write to be performed as two 32-bit operations.

A racing read could theoretically observe a mixture of two different writes:

```java
long value; // the specification permits a torn read or write
```

Declare the field `volatile` when independent shared reads and writes require atomicity and visibility:

```java
volatile long value;
```

Use `AtomicLong` when compound atomic operations are required:

```java
AtomicLong counter = new AtomicLong();
counter.incrementAndGet();
```

## Summary

- Java forbids word tearing between distinct fields and array elements.
- This guarantee does not prevent races on the same variable.
- Non-`volatile` `long` and `double` have a separate specification-level tearing exception.
- Use `volatile`, synchronization, locks, or atomic classes according to the required operation.

## Official reference

- [JLS 17.6: Word Tearing](https://docs.oracle.com/javase/specs/jls/se25/html/jls-17.html#jls-17.6)
- [JLS 17.7: Non-Atomic Treatment of `double` and `long`](https://docs.oracle.com/javase/specs/jls/se25/html/jls-17.html#jls-17.7)
