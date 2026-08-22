# Syntax. Flexible Constructor Bodies

## Front

What are flexible constructor bodies, and what may appear before `super(...)` or `this(...)` in modern Java?

## Back

**Flexible constructor bodies became final in JDK 25** with JEP 513.

| JDK | Status |
|---|---|
| 22 | First preview — JEP 447 |
| 23 | Second preview — JEP 482 |
| 24 | Third preview — JEP 492 |
| 25 | Final — JEP 513 |

Before this feature, an explicit `super(...)` or `this(...)` invocation had to be the first statement in a constructor.

Modern Java allows safe statements before that invocation.

## Validate arguments before `super(...)`

```java
class Person {
    Person(String name, int age) {
    }
}

class Employee extends Person {
    Employee(String name, int age) {
        if (age < 18) {
            throw new IllegalArgumentException("Employee must be an adult");
        }

        super(name, age);
    }
}
```

The validation happens before the superclass constructor runs.

## Compute superclass arguments first

```java
class User extends Person {
    User(String name, int age) {
        String normalizedName = name.strip();

        if (normalizedName.isEmpty()) {
            throw new IllegalArgumentException("Name is empty");
        }

        super(normalizedName, age);
    }
}
```

This avoids placing complex validation or computation inside the `super(...)` argument list.

## Initialize fields before superclass construction

```java
class Account extends BaseAccount {
    private final UUID auditId;

    Account(String owner) {
        this.auditId = UUID.randomUUID();
        super(owner);
    }
}
```

The language permits controlled initialization of fields declared by the class before the superclass constructor is invoked.

## Safety restrictions

The statements before `super(...)` or `this(...)` form the constructor **prologue**. During this phase, the object is not fully initialized.

The prologue cannot use the object in ways that could expose its uninitialized state. In particular, code cannot:

- Invoke instance methods on `this`.
- Access inherited instance state.
- Pass `this` to other code.
- Use the object before superclass construction has completed.

```java
class Child extends Parent {
    Child() {
        printState(); // compile-time error: unsafe use before super()
        super();
    }
}
```

## Summary

Flexible constructor bodies allow validation, computation, and safe field initialization before `super(...)` or `this(...)`. The compiler still prevents access that could expose a partially constructed object.

## Official references

- [JEP 447: Statements before `super(...)` — Preview, JDK 22](https://openjdk.org/jeps/447)
- [JEP 482: Flexible Constructor Bodies — Second Preview, JDK 23](https://openjdk.org/jeps/482)
- [JEP 492: Flexible Constructor Bodies — Third Preview, JDK 24](https://openjdk.org/jeps/492)
- [JEP 513: Flexible Constructor Bodies — JDK 25](https://openjdk.org/jeps/513)
