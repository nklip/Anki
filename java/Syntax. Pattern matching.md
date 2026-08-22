# Syntax. Pattern Matching

## Front

What is pattern matching in modern Java, and when were its main forms added?

## Back

Pattern matching combines a test with the conditional extraction of values.

Java introduced it in stages:

| Feature | Final JDK | Preview history |
|---|---:|---|
| Pattern matching for `instanceof` | **JDK 16** | JDK 14–15 |
| Record patterns | **JDK 21** | JDK 19–20 |
| Pattern matching for `switch` | **JDK 21** | JDK 17–20 |

## Type patterns with `instanceof`

Before pattern matching:

```java
if (value instanceof String) {
    String text = (String) value;
    System.out.println(text.length());
}
```

With a type pattern:

```java
if (value instanceof String text) {
    System.out.println(text.length());
}
```

The pattern performs three operations:

1. Tests whether `value` is a `String`.
2. Casts it to `String` when the test succeeds.
3. Assigns it to the pattern variable `text`.

Pattern variables use **flow-sensitive scope**:

```java
if (value instanceof String text && !text.isBlank()) {
    System.out.println(text);
}
```

`text` is in scope only where the compiler knows the pattern matched.

## Pattern matching for `switch`

JDK 21 allows type patterns in `switch`:

```java
static String describe(Object value) {
    return switch (value) {
        case null -> "null";
        case Integer number -> "integer: " + number;
        case String text when text.isBlank() -> "blank string";
        case String text -> "string: " + text;
        default -> "other";
    };
}
```

Important rules:

- The first applicable case is selected.
- A broader pattern cannot appear before a narrower pattern that it dominates.
- A `when` guard adds an extra boolean condition.
- A `switch` expression must be exhaustive.
- `case null` handles `null` explicitly.

Invalid order:

```java
return switch (value) {
    case CharSequence sequence -> sequence.length();
    case String text -> text.length(); // error: dominated
    default -> 0;
};
```

`String` is already covered by the earlier `CharSequence` case.

## Record patterns

JDK 21 record patterns deconstruct record values directly:

```java
record Point(int x, int y) {}

static int distanceSquared(Object value) {
    if (value instanceof Point(int x, int y)) {
        return x * x + y * y;
    }
    return 0;
}
```

They can be nested:

```java
record Point(int x, int y) {}
record Line(Point start, Point end) {}

static int startX(Line line) {
    return switch (line) {
        case Line(Point(int x, int y), Point end) -> x;
    };
}
```

## Summary

Pattern matching makes type checks, casts, deconstruction, and type-based branching shorter and safer. The key modern forms are `instanceof` patterns from JDK 16 and record/switch patterns from JDK 21.

## Official references

- [JEP 394: Pattern Matching for `instanceof` — JDK 16](https://openjdk.org/jeps/394)
- [JEP 440: Record Patterns — JDK 21](https://openjdk.org/jeps/440)
- [JEP 441: Pattern Matching for `switch` — JDK 21](https://openjdk.org/jeps/441)

