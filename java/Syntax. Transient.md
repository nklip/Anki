# Modifiers. `transient`

## Front

What does the `transient` keyword mean in Java?

## Back

`transient` marks an instance field that should be skipped by Java's default serialization mechanism.

```java
import java.io.Serializable;

class UserSession implements Serializable {
    private String username;
    private transient String accessToken;
}
```

When a `UserSession` is serialized:

- `username` is written to the serialized form.
- `accessToken` is not written.

## Value after deserialization

A transient field receives its type's default value because constructors and field initializers are normally not used during deserialization:

| Field type | Value after deserialization |
|---|---|
| Reference | `null` |
| `boolean` | `false` |
| Numeric primitive | `0` |

```java
UserSession restored = deserialize(data);

System.out.println(restored.getUsername());    // saved username
System.out.println(restored.getAccessToken()); // null
```

## Typical uses

Use `transient` for fields that:

- Contain temporary or derived data.
- Should be recalculated after deserialization.
- Refer to objects that are not serializable.
- Should not be included in the default serialized form.

```java
class Report implements Serializable {
    private List<Integer> values;
    private transient int cachedTotal;
}
```

## Important rules

- `transient` applies only to instance fields.
- `static` fields belong to the class and are not serialized, even without `transient`.
- `transient` affects Java object serialization; it does not make a value invisible in memory.
- It is not a security or encryption mechanism.
- Custom `writeObject()` and `readObject()` methods can explicitly write and restore a transient field.

## Not the same as JPA `@Transient`

```java
@jakarta.persistence.Transient
private String displayName;
```

JPA's `@Transient` tells a persistence provider not to map a field to the database. Java's `transient` keyword controls default object serialization. They solve different problems.

## Summary

`transient` excludes an instance field from Java's default serialized form. After deserialization, the field normally contains its default value and must be restored or recalculated if needed.
