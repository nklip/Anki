# Syntax. Sealed Classes

## Front

What are sealed classes and interfaces, when were they added, and how do `sealed`, `final`, and `non-sealed` work together?

## Back

**Sealed classes became final in JDK 17** through JEP 409. They were preview features in JDK 15 and JDK 16.

A sealed class or interface explicitly restricts which types may directly extend or implement it.

```java
sealed interface Shape
        permits Circle, Rectangle, Polygon {
}

final class Circle implements Shape {
}

sealed class Rectangle implements Shape
        permits FilledRectangle {
}

final class FilledRectangle extends Rectangle {
}

non-sealed class Polygon implements Shape {
}
```

Every permitted **direct subtype** must choose one of three modifiers:

| Modifier | Meaning |
|---|---|
| `final` | The hierarchy stops at this subtype |
| `sealed` | The subtype continues the restricted hierarchy and declares its permitted subtypes |
| `non-sealed` | The subtype reopens this branch for unrestricted extension |

## Meaning of each branch

```java
final class Circle implements Shape {
}
```

No class can extend `Circle`.

```java
sealed class Rectangle implements Shape
        permits FilledRectangle {
}
```

Only `FilledRectangle` may directly extend `Rectangle`.

```java
non-sealed class Polygon implements Shape {
}
```

Any permitted class may extend `Polygon` because this branch is open again.

## `permits` can sometimes be inferred

When all direct subtypes are declared in the same source file, the compiler can infer the permitted list:

```java
sealed interface Result {}

record Success(String value) implements Result {}
record Failure(String message) implements Result {}
```

Records are implicitly final, so they satisfy the permitted-subtype requirement.

## Exhaustive pattern matching

A sealed hierarchy gives the compiler a known set of alternatives. This works especially well with pattern matching for `switch` from JDK 21:

```java
static double area(Shape shape) {
    return switch (shape) {
        case Circle circle -> calculateCircle(circle);
        case Rectangle rectangle -> calculateRectangle(rectangle);
        case Polygon polygon -> calculatePolygon(polygon);
    };
}
```

No `default` is required when the compiler can prove that all permitted alternatives are covered.

## Placement rule

Permitted direct subtypes must be accessible to the sealed parent and must be located:

- In the same named module, or
- In the same package when using the unnamed module.

## Summary

Use sealed hierarchies when the domain has a controlled set of variants. `final` closes a branch, `sealed` continues the restriction, and `non-sealed` deliberately reopens a branch.

## Official reference

- [JEP 409: Sealed Classes — JDK 17](https://openjdk.org/jeps/409)

