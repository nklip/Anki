# Syntax. Module Import Declarations

## Front

What does `import module` do in Java, and how is it different from an ordinary import or `requires`?

## Back

**Module import declarations became final in JDK 25** with JEP 511.

| JDK | Status |
|---|---|
| 23 | First preview — JEP 476 |
| 24 | Second preview — JEP 494 |
| 25 | Final — JEP 511 |

A module import makes the public top-level types in packages exported by a module available to one compilation unit:

```java
import module java.base;

void printNames(List<String> names) {
    names.stream()
         .map(String::trim)
         .forEach(System.out::println);
}
```

Without the module import, this file would need individual package imports such as `java.util.List`.

## Transitive exports

The import also covers exported packages from modules read through transitive dependencies:

```java
import module java.sql;

Connection open(DataSource source) throws SQLException {
    return source.getConnection();
}
```

`java.sql` exports JDBC types and transitively requires `java.transaction.xa` and `java.xml`.

## Resolving name conflicts

Importing many packages can expose types with the same simple name. Add a more specific import to resolve the ambiguity:

```java
import module java.base;
import module java.sql;
import java.sql.Date;

Date createdOn;
```

The single-type import selects `java.sql.Date` instead of `java.util.Date`.

## `import module` is not `requires`

```java
// In a source file: makes exported type names available in this file
import module java.sql;
```

```java
// In module-info.java: declares a dependency between named modules
requires java.sql;
```

A module import does not replace a dependency declaration in `module-info.java`.

## Important rules

- It imports accessible public top-level types from exported packages.
- It does not expose types from non-exported packages.
- It does not import static members.
- It can be used in modular and non-modular source code.
- A normal single-type import can resolve a simple-name collision.

## Summary

`import module` is a concise way to import the API exported by an entire module into one source file. It is especially useful for small programs and broad APIs, but ordinary imports can communicate dependencies more precisely.

## Official references

- [JEP 476: Module Import Declarations — Preview, JDK 23](https://openjdk.org/jeps/476)
- [JEP 494: Module Import Declarations — Second Preview, JDK 24](https://openjdk.org/jeps/494)
- [JEP 511: Module Import Declarations — JDK 25](https://openjdk.org/jeps/511)

