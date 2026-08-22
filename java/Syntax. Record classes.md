# Syntax. Record Classes

## Front

What is a Java record class, when was it added, and what does the compiler generate?

## Back

**Record classes became final in JDK 16** through JEP 395. They were preview features in JDK 14 and JDK 15.

A record is a concise class for transparent data carriers:

```java
record Point(int x, int y) {}
```

The record header declares the complete state of the record.

For each component, the compiler provides:

- A private final field.
- A public accessor with the component's name.
- A canonical constructor.
- Value-based `equals()` and `hashCode()`.
- A readable `toString()`.

```java
Point point = new Point(10, 20);

int x = point.x(); // accessor is x(), not getX()
int y = point.y();

System.out.println(point); // Point[x=10, y=20]
```

## Compact constructor

Use a compact canonical constructor for validation and normalization:

```java
record User(String name, int age) {
    User {
        Objects.requireNonNull(name);

        if (age < 0) {
            throw new IllegalArgumentException("age must be non-negative");
        }

        name = name.trim();
    }
}
```

The compiler assigns the final component fields after the compact constructor body.

## Records can contain behavior

```java
record Rectangle(double width, double height) {
    double area() {
        return width * height;
    }

    static Rectangle square(double side) {
        return new Rectangle(side, side);
    }
}
```

Records can:

- Implement interfaces.
- Declare methods and static members.
- Override generated accessors when necessary.
- Be generic.

```java
record Pair<L, R>(L left, R right) {}
```

Records cannot:

- Extend another class; they implicitly extend `java.lang.Record`.
- Declare additional instance fields outside their components.
- Be extended; record classes are implicitly final.

## Shallow immutability

The component references are final, but referenced objects may still be mutable:

```java
record Team(List<String> members) {}

var names = new ArrayList<>(List.of("Alice"));
var team = new Team(names);

names.add("Bob"); // team.members() now also contains Bob
```

Make defensive copies when true immutability is required:

```java
record Team(List<String> members) {
    Team {
        members = List.copyOf(members);
    }
}
```

## Summary

Records remove boilerplate for data-focused classes, but they do not automatically make mutable component objects immutable.

## Official reference

- [JEP 395: Records — JDK 16](https://openjdk.org/jeps/395)

