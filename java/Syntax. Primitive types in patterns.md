# Syntax. Primitive Types in Patterns

## Front

How can primitive types be used in patterns and `switch`, and is this syntax final?

## Back

**Primitive types in patterns are still a preview feature.**

| JDK | Status |
|---|---|
| 23 | First preview — JEP 455 |
| 24 | Second preview — JEP 488 |
| 25 | Third preview — JEP 507 |
| 26 | Fourth preview — JEP 530 |

Preview features require `--enable-preview` and may change before becoming final.

## Primitive patterns with `instanceof`

A primitive pattern tests whether a value can be converted exactly to the target primitive type:

```java
int value = 100;

if (value instanceof byte small) {
    System.out.println(small); // 100 fits exactly in byte
}
```

If the value cannot be represented exactly, the pattern does not match:

```java
int value = 1_000;

if (value instanceof byte small) {
    // not entered: 1,000 does not fit in byte
}
```

## More primitive `switch` selectors

The preview extends `switch` so that selectors can use primitive types such as `long`, `float`, `double`, and `boolean`:

```java
long status = 1L;

String text = switch (status) {
    case 0L -> "stopped";
    case 1L -> "running";
    case long other -> "unknown: " + other;
};
```

A `boolean` switch can express an exhaustive choice:

```java
String answer = switch (ready) {
    case true  -> "ready";
    case false -> "not ready";
};
```

## Compiling preview code

For JDK 26:

```text
javac --release 26 --enable-preview Main.java
java --enable-preview Main
```

Use the corresponding release number when compiling with JDK 23, 24, or 25.

## Important rules

- A primitive pattern matches only when the conversion is exact.
- The feature expands pattern matching and the primitive types accepted by `switch`.
- Code that uses it is tied to the preview version with which it was compiled.
- Do not treat preview syntax as a permanent Java language guarantee.

## Summary

Primitive patterns make numeric range and exact-conversion checks concise, while expanded `switch` selectors reduce manual `if` chains. As of JDK 26, the feature is **not final**.

## Official references

- [JEP 455: Primitive Types in Patterns, `instanceof`, and `switch` — JDK 23](https://openjdk.org/jeps/455)
- [JEP 488: Primitive Types in Patterns, `instanceof`, and `switch` — Second Preview, JDK 24](https://openjdk.org/jeps/488)
- [JEP 507: Primitive Types in Patterns, `instanceof`, and `switch` — Third Preview, JDK 25](https://openjdk.org/jeps/507)
- [JEP 530: Primitive Types in Patterns, `instanceof`, and `switch` — Fourth Preview, JDK 26](https://openjdk.org/jeps/530)

