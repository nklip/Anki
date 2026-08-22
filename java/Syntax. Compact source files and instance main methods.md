# Syntax. Compact Source Files and Instance Main Methods

## Front

What are compact source files and instance `main` methods in modern Java?

## Back

**Compact source files and instance `main` methods became final in JDK 25** with JEP 512.

| JDK | Status |
|---|---|
| 21 | First preview — JEP 445 |
| 22 | Second preview — JEP 463 |
| 23 | Third preview — JEP 477 |
| 24 | Fourth preview — JEP 495 |
| 25 | Final — JEP 512 |

## Compact source file

A small program no longer needs an explicit class declaration or the traditional `public static void main(String[] args)` ceremony:

```java
void main() {
    System.out.println("Hello, World!");
}
```

The compiler supplies an implicit class for the source file, and the launcher invokes its instance `main` method.

## Fields and helper methods

A compact source file may also contain fields and methods:

```java
String greeting = "Hello";

void main() {
    printGreeting("Alice");
}

void printGreeting(String name) {
    System.out.println(greeting + ", " + name);
}
```

This is still a class-based Java program; the class declaration is implicit.

## Instance `main` in an ordinary class

An explicitly declared class can also have an instance `main` method:

```java
class Application {
    void main() {
        System.out.println("Started");
    }
}
```

The traditional entry point remains valid:

```java
public class Application {
    public static void main(String[] args) {
        System.out.println("Started");
    }
}
```

## Automatic imports

Compact source files automatically have access to public top-level types exported by `java.base`, as if the file contained:

```java
import module java.base;
```

This makes common types such as `List`, `Map`, and `Path` easier to use in small programs.

## When to use it

Compact source files are well suited to:

- Learning and teaching Java.
- Small utilities and experiments.
- Programs that do not yet need an explicit class structure.

Use ordinary named classes when the class itself is part of a reusable API or when explicit structure improves the design.

## Summary

Modern Java can start with `void main()` and no explicit class. The familiar class declaration and static `main` method are still supported, so a small program can grow into a conventional application gradually.

## Official references

- [JEP 445: Unnamed Classes and Instance Main Methods — Preview, JDK 21](https://openjdk.org/jeps/445)
- [JEP 463: Implicitly Declared Classes and Instance Main Methods — Second Preview, JDK 22](https://openjdk.org/jeps/463)
- [JEP 477: Implicitly Declared Classes and Instance Main Methods — Third Preview, JDK 23](https://openjdk.org/jeps/477)
- [JEP 495: Simple Source Files and Instance Main Methods — Fourth Preview, JDK 24](https://openjdk.org/jeps/495)
- [JEP 512: Compact Source Files and Instance Main Methods — JDK 25](https://openjdk.org/jeps/512)

