# Syntax. Markdown Documentation Comments

## Front

How do Markdown documentation comments work in modern Java?

## Back

**Markdown documentation comments were added in JDK 23** by JEP 467.

They begin with `///`. Each consecutive `///` line belongs to the same documentation comment:

```java
/// # User service
///
/// Creates and manages application users.
///
/// - Thread-safe
/// - Caches successful lookups
public final class UserService {
}
```

The standard `javadoc` tool renders the Markdown as API documentation.

## Methods and Javadoc tags

Markdown comments can use ordinary Markdown together with Javadoc block and inline tags:

```java
/// Adds two numbers.
///
/// Use {@link Math#addExact(int, int)} instead when the caller
/// requires overflow checking.
///
/// @param left the first number
/// @param right the second number
/// @return the sum
static int add(int left, int right) {
    return left + right;
}
```

Traditional inline tags also remain available:

```java
/// Returns an immutable {@link java.util.List}.
```

## Traditional comments still work

JDK 23 did not remove the original Javadoc syntax:

```java
/**
 * Returns the current user.
 *
 * @return the current user
 */
User currentUser() {
    return user;
}
```

Both styles can coexist in the same project.

## Important rules

- A Markdown documentation comment uses consecutive lines beginning with `///`.
- Markdown formatting is interpreted by the standard doclet.
- Javadoc tags such as `@param`, `@return`, `@throws`, and `{@link ...}` are supported.
- The feature affects source documentation only; it does not change runtime behavior.
- `//` is still an ordinary comment and does not create API documentation.

## Summary

Use `///` when Markdown makes documentation easier to write and read. Existing `/** ... */` Javadoc comments remain fully supported.

## Official reference

- [JEP 467: Markdown Documentation Comments — JDK 23](https://openjdk.org/jeps/467)
