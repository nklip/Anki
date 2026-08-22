# Autoboxing and Unboxing in Modern Java

## Front

What are **autoboxing** and **unboxing** in Java?

Explain when they occur, their null and equality pitfalls, wrapper caching, effects on generics and overload resolution, performance implications, and modern value-based-class guidance.

## Back

**Autoboxing** is the compiler-supported conversion of a primitive value into its corresponding wrapper reference type.

```java
int primitive = 42;
Integer boxed = primitive; // autoboxing: int → Integer
```

**Unboxing** is the conversion of a wrapper reference into its corresponding primitive value.

```java
Integer boxed = 42;
int primitive = boxed; // unboxing: Integer → int
```

Conceptually, these resemble explicit method calls:

```java
Integer boxed = Integer.valueOf(primitive);
int value = boxed.intValue();
```

The <b>Java Language Specification</b> ( <b>JLS</b> ) defines the conversion semantics. Source-level autoboxing should not be understood as a guarantee that the compiler literally emits those exact method calls in every situation.

## Primitive and wrapper pairs

| Primitive | Wrapper | Explicit unboxing method |
|---|---|---|
| `boolean` | `Boolean` | `booleanValue()` |
| `byte` | `Byte` | `byteValue()` |
| `short` | `Short` | `shortValue()` |
| `char` | `Character` | `charValue()` |
| `int` | `Integer` | `intValue()` |
| `long` | `Long` | `longValue()` |
| `float` | `Float` | `floatValue()` |
| `double` | `Double` | `doubleValue()` |

Wrapper objects are immutable. A wrapper reference may still be reassigned:

```java
Integer number = 10;
number = 20;
```

The value inside an existing `Integer` was not mutated. `number` now refers to a wrapper representing another value.

## Where automatic conversion occurs

### Assignment

```java
Integer boxed = 42; // boxing
int value = boxed;  // unboxing
```

### Method arguments and return values

```java
static void acceptInteger(Integer value) {}

acceptInteger(42); // boxes int to Integer
```

```java
static int primitiveResult() {
    Integer result = 42;
    return result; // unboxes Integer to int
}
```

### Generic collections

Generic type arguments must be reference types:

```java
List<Integer> numbers = new ArrayList<>();

numbers.add(42);       // boxes int to Integer
int first = numbers.get(0); // unboxes Integer to int
```

This is illegal:

```java
// List<int> numbers; // does not compile
```

### Arithmetic and numeric operators

```java
Integer left = 10;
Integer right = 20;

int sum = left + right;
```

Both operands are unboxed before addition. The result of the arithmetic expression is a primitive `int`.

```java
var sum = left + right;

// sum is int, not Integer
```

### Increment and decrement

```java
Integer count = 0;
count++;
```

Conceptually:

```text
unbox Integer to int
        ↓
add 1 as primitive arithmetic
        ↓
box the result into Integer
        ↓
assign the new reference to count
```

This does not mutate an `Integer` object. It replaces the reference.

It is also not an atomic concurrent increment. Use `AtomicInteger`, `LongAdder`, or locking when threads update a shared counter.

### Conditions

```java
Boolean enabled = true;

if (enabled) { // unboxes Boolean to boolean
    start();
}
```

### Comparisons with a primitive operand

```java
Integer boxed = 1_000;

System.out.println(boxed == 1_000); // true: boxed is unboxed
```

This is numeric comparison, not wrapper-reference identity comparison, because one operand is primitive.

## The most important unboxing hazard: `null`

Unboxing a null wrapper throws `NullPointerException`:

```java
Integer boxed = null;
int value = boxed; // NullPointerException
```

Conceptually, Java attempts:

```java
boxed.intValue();
```

The method cannot be invoked through a null reference.

### Nullable `Boolean`

```java
Boolean enabled = null;

if (enabled) { // NullPointerException
    start();
}
```

Null-safe test:

```java
if (Boolean.TRUE.equals(enabled)) {
    start();
}
```

This treats `null` as false.

If the application has only two meaningful states, prefer primitive `boolean`. Use `Boolean` when the third state—unknown or unset—is intentional.

### Nullable collection result

```java
Map<String, Integer> scores = new HashMap<>();

int score = scores.get("Alice"); // NullPointerException if absent
```

`Map.get()` returns `null` for an absent mapping, and assignment to `int` attempts to unbox it.

Handle absence explicitly:

```java
Integer boxedScore = scores.get("Alice");

if (boxedScore != null) {
    int score = boxedScore;
}
```

Or choose a meaningful default:

```java
int score = scores.getOrDefault("Alice", 0);
```

Be careful: if the map explicitly contains a key mapped to `null`, `getOrDefault()` returns that null value, and unboxing still fails.

### Nullable method result

```java
static Integer findScore() {
    return null;
}

int score = findScore(); // NullPointerException
```

The exception occurs at the implicit unboxing site, which may be far from the method that produced `null`.

### Comparison with a primitive

```java
Integer result = null;

if (result == 0) { // NullPointerException
}
```

The comparison requires `result` to be unboxed.

Checking the reference itself is safe:

```java
if (result == null) {
}
```

### Conditional operator

Numeric conditional expressions may require unboxing:

```java
Integer boxed = null;
boolean useBoxed = true;

int result = useBoxed ? boxed : 0; // NullPointerException
```

The selected `boxed` operand must be converted to the primitive numeric result type.

## Wrapper equality and identity

### `==` between two wrappers compares references

```java
Integer first = 1_000;
Integer second = 1_000;

System.out.println(first == second);
```

Both operands are references, so `==` compares identity. The result must not be used as a value comparison.

Use:

```java
System.out.println(first.equals(second)); // true
```

For nullable references:

```java
System.out.println(Objects.equals(first, second));
```

### Wrapper caches make `==` especially misleading

```java
Integer first = 127;
Integer second = 127;

System.out.println(first == second); // true
```

The JLS requires identical boxing results for constant-expression values in these ranges:

- `true` and `false`.
- Every `byte` value.
- Characters from `\u0000` through `\u007f`.
- Integral values from `-128` through `127` for `short`, `int`, and `long` boxing.

Implementations may cache additional values:

```java
Integer first = 128;
Integer second = 128;

System.out.println(first == second); // identity must not be assumed
```

It is commonly `false`, but Java code must not depend on that. An implementation is permitted to share additional wrapper instances.

The correct rule is simple:

```text
compare wrapper values with equals(), not ==
```

### Primitive comparison forces unboxing

```java
Integer first = 1_000;
int second = 1_000;

System.out.println(first == second); // true
```

Because one operand is primitive, `first` is unboxed and the primitive values are compared.

### Different wrapper types are not numerically equal

```java
Integer integer = 1;
Long longValue = 1L;

System.out.println(integer.equals(longValue)); // false
```

Wrapper `equals()` methods normally require the same wrapper type as well as the same value.

For deliberate cross-type numeric comparison, convert to a common primitive type while considering range and floating-point semantics:

```java
System.out.println(integer.longValue() == longValue.longValue());
```

## Modern wrappers are value-based classes

The eight primitive wrapper classes are specified as **value-based classes**.

Treat equal wrapper values as interchangeable and do not depend on object identity through:

- `==` or `!=` between wrapper references.
- `System.identityHashCode(wrapper)`.
- Identity-based collections.
- Synchronization on wrapper instances.
- Assumptions that a factory returns a fresh object.

### Do not synchronize on wrappers

```java
Integer lock = 42;

synchronized (lock) { // warning: synchronization on a value-based class
    updateState();
}
```

This is broken design because wrapper objects may be shared through caching and wrapper identity is intentionally unreliable. Modern `javac` warns about synchronization on value-based classes.

Use a dedicated stable lock:

```java
private final Object lock = new Object();

void update() {
    synchronized (lock) {
        updateState();
    }
}
```

## Wrapper constructors are deprecated for removal

Do not write:

```java
Integer number = new Integer(42); // deprecated for removal
Double value = new Double(3.14);  // deprecated for removal
```

Use boxing or a factory:

```java
Integer number = 42;
Integer explicit = Integer.valueOf(42);

Double value = 3.14;
Double explicitDouble = Double.valueOf(3.14);
```

Wrapper constructors were deprecated in Java 9 and designated for removal as part of the value-based-class migration guidance. `valueOf()` permits instance reuse and expresses value semantics.

As of Java 26, wrappers are still ordinary API classes, but code should already avoid identity-sensitive behavior.

## Parsing is not boxing

`parseInt()` returns a primitive:

```java
int primitive = Integer.parseInt("42");
```

`valueOf()` returns a wrapper:

```java
Integer boxed = Integer.valueOf("42");
```

Both may throw `NumberFormatException` for invalid input.

Use the primitive-returning parser when a wrapper is unnecessary.

## Numeric conversions around boxing

### Unboxing followed by primitive widening is allowed

```java
Integer integer = 42;
long value = integer; // Integer → int → long
```

### Boxing to one wrapper does not convert into another wrapper

```java
// Long value = 42; // does not compile
```

The `int` literal would box to `Integer`; Java does not then convert that wrapper into `Long`.

Use the correct primitive type:

```java
Long value = 42L;
```

Or perform an explicit numeric conversion before boxing:

```java
Long value = Long.valueOf(42);
```

### Boxing followed by widening reference conversion is allowed

```java
Number number = 42; // int → Integer → Number
Object object = true; // boolean → Boolean → Object
```

The runtime objects are `Integer` and `Boolean`, respectively.

## Autoboxing and overload resolution

Method overload resolution occurs in phases. Java first looks for an applicable fixed-arity method without boxing or unboxing. Only if that fails does it consider boxing and unboxing; variable-arity invocation is considered later.

### Primitive widening is preferred over boxing

```java
static void select(long value) {
    System.out.println("long");
}

static void select(Integer value) {
    System.out.println("Integer");
}

select(42); // prints: long
```

`int` to `long` is available during the earlier strict-invocation phase. Boxing to `Integer` is considered only in a later phase.

### Exact reference type avoids unboxing

```java
static void select(Integer value) {
    System.out.println("Integer");
}

static void select(int value) {
    System.out.println("int");
}

Integer number = 42;
select(number); // prints: Integer
```

The exact reference match is applicable without unboxing.

### Null and overloaded wrappers

```java
static void process(Integer value) {}
static void process(Long value) {}

// process(null); // ambiguous
```

`null` is compatible with both unrelated reference types, so neither overload is more specific.

Avoid overload sets where primitive/wrapper distinctions make calls surprising.

## The `List<Integer>.remove()` trap

`List` overloads `remove`:

```java
E remove(int index);
boolean remove(Object value);
```

For a list of integers:

```java
List<Integer> numbers = new ArrayList<>(
        List.of(10, 20, 30)
);

numbers.remove(1); // removes index 1: value 20
```

To remove the value `1`:

```java
numbers.remove(Integer.valueOf(1));
```

The primitive `int` argument selects the index overload. Boxing is not considered because an applicable primitive overload already exists.

## Arrays and boxed collections

Primitive and wrapper arrays are different types:

```java
int[] primitives = {1, 2, 3};
Integer[] wrappers = {1, 2, 3};
```

Java does not automatically convert the complete array between `int[]` and `Integer[]`.

### `Arrays.asList()` with a primitive array

```java
int[] values = {1, 2, 3};

List<int[]> list = Arrays.asList(values);
System.out.println(list.size()); // 1
```

The single list element is the entire `int[]`. The varargs parameter is `T...`, and a primitive array can be one reference-valued argument; its elements are not individually boxed.

To create boxed elements:

```java
List<Integer> list = Arrays.stream(values)
        .boxed()
        .toList();
```

The result of `Stream.toList()` is unmodifiable.

For a mutable list:

```java
List<Integer> mutable = Arrays.stream(values)
        .boxed()
        .collect(Collectors.toCollection(ArrayList::new));
```

## Primitive streams avoid unnecessary boxing

This pipeline processes wrapper elements:

```java
Stream<Integer> boxed = Stream.of(1, 2, 3);
int sum = boxed.mapToInt(Integer::intValue).sum();
```

When the source is primitive-oriented, prefer `IntStream`, `LongStream`, or `DoubleStream`:

```java
int sum = IntStream.rangeClosed(1, 1_000_000)
        .sum();
```

Box only when an API actually requires objects:

```java
List<Integer> values = IntStream.range(0, 100)
        .boxed()
        .toList();
```

Useful primitive-specialized APIs include:

- `IntStream`, `LongStream`, and `DoubleStream`.
- `OptionalInt`, `OptionalLong`, and `OptionalDouble`.
- `ToIntFunction`, `IntFunction`, `IntPredicate`, and related functional interfaces.
- `Comparator.comparingInt`, `comparingLong`, and `comparingDouble`.
- `AtomicInteger`, `AtomicLong`, and primitive atomic arrays.

Example avoiding boxed sort keys:

```java
users.sort(Comparator.comparingInt(User::age));
```

## Performance and memory implications

Primitive values can often live directly in local variables, arrays, registers, or object fields. Wrapper values are references and may require separate objects.

Potential boxing costs include:

- Wrapper allocation when a cached object is unavailable and allocation is not eliminated.
- Garbage-collection pressure.
- Extra references in collections and arrays.
- Pointer indirection and reduced memory locality.
- Null checks during unboxing.
- Cache-coherence or synchronization mistakes when identity is misused.

The JIT compiler may eliminate some wrapper allocations through escape analysis and other optimizations. Small cached values may also reuse existing instances. Neither behavior should be required for correctness or assumed in performance-sensitive code.

### Hidden boxing in a loop

```java
Integer sum = 0;

for (int i = 0; i < 1_000_000; i++) {
    sum += i;
}
```

Each iteration conceptually unboxes `sum`, performs primitive addition, and boxes the new result.

Prefer:

```java
int sum = 0;

for (int i = 0; i < 1_000_000; i++) {
    sum += i;
}
```

Use a wrapper when nullability, generics, reflection, or an object-based API genuinely requires one.

## Modern switch and nullable wrappers

A wrapper selector may be null. Without explicit null handling, switching on it throws `NullPointerException`:

```java
Integer status = null;

// Throws NullPointerException without a matching case null
String label = switch (status) {
    case 200 -> "OK";
    default -> "Other";
};
```

Modern pattern-switch semantics allow explicit null handling for a reference selector:

```java
String label = switch (status) {
    case null -> "Unknown";
    case 200 -> "OK";
    default -> "Other";
};
```

This does not change the general rule that unboxing `null` throws `NullPointerException`.

## Choosing primitives or wrappers

Prefer primitives when:

- Null is not a meaningful state.
- Performing numeric or boolean computation.
- Working in performance-sensitive loops.
- Storing large primitive arrays.
- An API provides primitive-specialized forms.

Use wrappers when:

- A generic type requires a reference type.
- Null intentionally represents missing, unknown, or unset.
- An object-based API requires a reference.
- A collection must store primitive-like values.
- Reflection or framework metadata requires the wrapper type.

Do not use a wrapper merely to make a value “more object-oriented.” Choose it because reference semantics or nullability are required.

## Common misconceptions

### “Autoboxing is free syntax with no runtime implications”

It simplifies source code, but conversions can introduce allocation, reference storage, cache behavior, garbage collection, and null failures.

### “Two equal boxed values are always the same object”

No. Some constant values have guaranteed shared boxing identities, and implementations may share more. Wrapper identity must not be used as value semantics.

### “Values above 127 are guaranteed to produce different wrappers”

No. Sharing outside the required cache range is implementation-dependent.

### “`Integer == Integer` compares numbers”

It compares references. `Integer == int` performs numeric comparison because the wrapper is unboxed.

### “A wrapper cannot cause `NullPointerException` during arithmetic”

Arithmetic, conditions, comparisons with primitives, return conversion, and increment can all implicitly unbox a null reference.

### “`Integer count++` mutates the Integer”

No. It unboxes, calculates, boxes, and reassigns the reference.

### “`List<Integer>.remove(1)` removes the value 1”

It invokes `remove(int index)`. Use `remove(Integer.valueOf(1))` to select value removal.

### “A volatile Integer makes increment atomic”

No. `volatile Integer count; count++;` still performs a separate read, unbox, calculation, box, and write. Use an atomic class or lock.

### “Wrapper constructors are the safest way to avoid caching”

Wrapper identity must not be part of the design. Their constructors are deprecated for removal; use boxing or `valueOf()`.

## Interview summary

> Autoboxing converts a primitive to its wrapper type, while unboxing converts a wrapper to its primitive value. The compiler applies these conversions in assignments, method calls, generics, operators, conditions, and other conversion contexts. Unboxing null throws `NullPointerException`. `==` between two wrapper references compares identity, while comparison with a primitive unboxes the wrapper. Some small constant values have guaranteed shared boxing identities, and implementations may cache more, so identity must never be used for wrapper value comparison. Modern wrappers are value-based classes: do not synchronize on them or call their deprecated-for-removal constructors. Boxing can also add allocation, memory, and GC costs; prefer primitives and primitive-specialized streams or functional interfaces when object semantics are unnecessary.

## Official references

- [JLS §5.1.7 — Boxing Conversion](https://docs.oracle.com/javase/specs/jls/se26/html/jls-5.html#jls-5.1.7)
- [JLS §5.1.8 — Unboxing Conversion](https://docs.oracle.com/javase/specs/jls/se26/html/jls-5.html#jls-5.1.8)
- [JLS §15.12.2 — Compile-Time Step 2: Determine Method Signature](https://docs.oracle.com/javase/specs/jls/se26/html/jls-15.html#jls-15.12.2)
- [JLS §14.11 — The `switch` Statement](https://docs.oracle.com/javase/specs/jls/se26/html/jls-14.html#jls-14.11)
- [Java SE 26 `Integer` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/lang/Integer.html)
- [JEP 390 — Warnings for Value-Based Classes](https://openjdk.org/jeps/390)
- [Java SE 26 `IntStream` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/stream/IntStream.html)
