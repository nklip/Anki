# Syntax. Switch Expression

## Front

What is a Java switch expression, when was it added, and how do arrow cases and `yield` work?

## Back

**Switch expressions became final in JDK 14** through JEP 361. They were preview features in JDK 12 and JDK 13.

A `switch` expression evaluates to a value:

```java
enum Status {
    NEW, RUNNING, DONE
}

String label = switch (status) {
    case NEW -> "New";
    case RUNNING -> "Running";
    case DONE -> "Done";
};
```

Important differences from a traditional switch statement:

- The result can be assigned or returned.
- Arrow cases do not fall through.
- Multiple labels can share one result.
- The cases must be exhaustive.
- The expression ends with a semicolon.

```java
int weekendValue = switch (day) {
    case SATURDAY, SUNDAY -> 1;
    default -> 0;
};
```

## `yield` from a block

Use `yield` when a case needs multiple statements before producing its value:

```java
int length = switch (value) {
    case "short" -> 5;
    case "calculate" -> {
        int result = expensiveCalculation();
        log(result);
        yield result;
    }
    default -> 0;
};
```

`yield` returns a value from the enclosing switch expression. It is not the same as `return`, which exits the method.

## Exhaustiveness

Every possible selector value must be handled:

```java
int priority = switch (status) {
    case NEW -> 1;
    case RUNNING -> 2;
    case DONE -> 3;
};
```

For an enum, listing every constant makes the expression exhaustive. For an open-ended type, a `default` case is normally required.

## Switch statement versus expression

Statement:

```java
switch (status) {
    case NEW -> start();
    case RUNNING -> monitor();
    case DONE -> finish();
}
```

Expression:

```java
String action = switch (status) {
    case NEW -> "start";
    case RUNNING -> "monitor";
    case DONE -> "finish";
};
```

The arrow-label syntax can be used by both forms, but only a switch expression produces a value.

## Summary

Switch expressions provide concise, exhaustive value selection without accidental fall-through. Use `yield` when one arm requires a block.

## Official reference

- [JEP 361: Switch Expressions — JDK 14](https://openjdk.org/jeps/361)

