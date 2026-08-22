# Thread-Safe Time Classes

## Front

Which Java date and time classes are thread-safe, and which ones should not be shared between threads?

## Back

## Practical rule

> Anything in `java.time` is safe to share as a constant; anything in `java.util` or `java.text` with a date in its name is not.

Treat this as a practical safety rule for choosing between modern and legacy date/time APIs.

## Modern API: `java.time`

Classes from `java.time` are immutable and thread-safe. They can safely be shared between threads and stored in constants:

```java
private static final DateTimeFormatter FORMATTER =
        DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

private static final ZoneId UTC = ZoneId.of("UTC");
```

Common thread-safe classes include:

- `Instant`
- `LocalDate`
- `LocalTime`
- `LocalDateTime`
- `ZonedDateTime`
- `Duration`
- `Period`
- `ZoneId`
- `DateTimeFormatter`

Operations return new values instead of modifying existing objects:

```java
LocalDate today = LocalDate.now();
LocalDate tomorrow = today.plusDays(1);

// today was not changed
```

## Legacy APIs: do not share mutable instances

Legacy date and formatting classes are mutable or not thread-safe:

```java
// Unsafe when shared by multiple threads
private static final SimpleDateFormat FORMATTER =
        new SimpleDateFormat("yyyy-MM-dd");
```

Important legacy examples:

- `java.util.Date` — mutable.
- `java.util.Calendar` — mutable and not thread-safe.
- `java.text.DateFormat` — not thread-safe.
- `java.text.SimpleDateFormat` — not thread-safe.

Prefer this:

```java
private static final DateTimeFormatter FORMATTER =
        DateTimeFormatter.ofPattern("yyyy-MM-dd");
```

If a legacy formatter must be used, create it locally or protect access with synchronization. Prefer migrating to `java.time` whenever possible.

## Summary

Use `java.time` for new code. Its immutable objects and thread-safe formatters can be shared safely. Do not share mutable legacy `Date`, `Calendar`, `DateFormat`, or `SimpleDateFormat` instances without synchronization.
