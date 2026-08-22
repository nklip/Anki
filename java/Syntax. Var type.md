# Syntax. `var` Type

## Front

What does `var` mean in Java, where can it be used, and what are its limitations?

## Back

**Local-variable type inference was added in JDK 10** by JEP 286.

`var` asks the compiler to infer a local variable's static type from its initializer:

```java
var name = "Alice";                  // String
var count = 10;                      // int
var users = new ArrayList<User>();   // ArrayList<User>
```

`var` does **not** make Java dynamically typed. The inferred type is fixed at compile time:

```java
var value = "text"; // inferred as String

value = "other";    // valid
value = 42;         // compile-time error
```

## Where `var` can be used

It can be used for local variables with initializers:

```java
var path = Path.of("data.txt");

for (var i = 0; i < 10; i++) {
    // i is int
}

for (var user : users) {
    // user has the collection element type
}

try (var input = Files.newInputStream(path)) {
    // input is InputStream
}
```

## Where `var` cannot be used

It cannot replace types for:

- Fields.
- Method or constructor parameters.
- Method return types.
- Variables without initializers.
- `catch` parameters.

```java
class Example {
    var field = 10;       // compile-time error

    var calculate() {     // compile-time error
        return 10;
    }

    void print(var text) { // compile-time error
    }
}
```

The initializer must provide enough type information:

```java
var missing;          // error: no initializer
var nothing = null;   // error: cannot infer a type
var numbers = {1, 2}; // error: array initializer needs a target type
```

Use an explicit type when it communicates intent better:

```java
List<User> users = new ArrayList<>();
```

With `var`, the inferred type is the concrete initializer type:

```java
var users = new ArrayList<User>(); // ArrayList<User>, not List<User>
```

## Lambda parameters

**JDK 11** extended `var` to implicitly typed lambda parameters, mainly so annotations can be added consistently:

```java
(var left, var right) -> left.compareTo(right)

(@Deprecated var value) -> value.trim()
```

If one lambda parameter uses `var`, all parameters must use it.

## Summary

`var` removes repeated local type declarations while preserving static typing. Use it when the inferred type is obvious; prefer an explicit type when `var` would hide important information.

## Official reference

- [JEP 286: Local-Variable Type Inference — JDK 10](https://openjdk.org/jeps/286)

