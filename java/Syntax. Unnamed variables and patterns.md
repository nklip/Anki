# Syntax. Unnamed Variables and Patterns

## Front

What are unnamed variables and unnamed patterns in Java, and when should `_` be used?

## Back

**Unnamed variables and patterns became final in JDK 22** with JEP 456. They were previewed in JDK 21.

The single underscore `_` means: **a value is required by the syntax, but this code does not use it**.

## Unnamed variables

An unnamed variable can be declared but cannot be read or assigned later:

```java
try {
    process();
} catch (IOException _) {
    logFailure();
}
```

It is useful in loops and lambdas when a value is intentionally ignored:

```java
for (var _ : tasks) {
    runNextTask();
}

users.forEach((_, user) -> save(user));
```

Multiple unnamed variables may appear in the same scope because none of them introduces a usable name:

```java
map.replaceAll((_, _) -> defaultValue);
```

## Unnamed patterns

Use `_` inside a record pattern to ignore a component:

```java
record Point(int x, int y) {}

if (value instanceof Point(int x, _)) {
    System.out.println(x); // y is intentionally ignored
}
```

Use an unnamed type pattern when only the matched type matters:

```java
switch (shape) {
    case Circle _   -> drawCircle();
    case Rectangle _ -> drawRectangle();
}
```

## Important rules

- `_` cannot be read; it does not hold an accessible value.
- It can represent an unused local variable, loop variable, resource, `catch` parameter, lambda parameter, or pattern.
- It cannot be used as a field, method parameter, constructor parameter, or ordinary identifier.
- Names containing an underscore, such as `_value`, are still ordinary identifiers.

```java
int _ = 10;       // error: `_` is not an ordinary identifier
int _value = 10;  // valid
```

## Summary

`_` documents that a required value is deliberately ignored. It reduces meaningless names such as `ignored`, `unused`, or `exception` and lets the compiler prevent accidental use.

## Official reference

- [JEP 456: Unnamed Variables and Patterns — JDK 22](https://openjdk.org/jeps/456)

