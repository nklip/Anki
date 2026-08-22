# Syntax. Text Block

## Front

What is a Java text block, when was it added, and how are indentation and line endings handled?

## Back

**Text blocks became final in JDK 15** through JEP 378. They were preview features in JDK 13 and JDK 14.

A text block is a multiline `String` literal enclosed by three double quotes:

```java
String json = """
        {
          "name": "Alice",
          "active": true
        }
        """;
```

It is still an ordinary `String`:

```java
System.out.println(json.getClass()); // class java.lang.String
```

Text blocks reduce escaping and concatenation:

```java
String html = """
        <html>
            <body>
                <p>Hello</p>
            </body>
        </html>
        """;
```

## Opening delimiter

The opening `"""` must be followed by optional whitespace and a line terminator:

```java
String valid = """
        text
        """;

String invalid = """text"""; // compile-time error
```

## Incidental indentation

The compiler removes common incidental indentation. The position of the closing delimiter helps determine the indentation boundary:

```java
String text = """
        first
          second
        third
        """;
```

The resulting content is conceptually:

```text
first
  second
third
```

## Trailing newline

Closing the block on its own line includes a newline after the last content line:

```java
String withNewline = """
        hello
        """;
```

Placing the closing delimiter immediately after the final content omits that trailing newline:

```java
String withoutNewline = """
        hello""";
```

## Useful escapes

Text blocks are **not raw strings**. Java escape sequences are still processed.

Use `\s` to preserve an intentional trailing space:

```java
String colors = """
        red  \s
        green\s
        blue \s
        """;
```

Use a backslash at the end of a source line to suppress the corresponding newline:

```java
String sentence = """
        This is one \
        logical line.
        """;
```

## Formatting values

Text blocks do not perform string interpolation. Use `formatted()` when values must be inserted:

```java
String template = """
        Hello, %s!
        You have %d messages.
        """;

String message = template.formatted(name, messageCount);
```

## Summary

Text blocks make multiline JSON, SQL, HTML, and other text easier to read. They produce ordinary strings, normalize line endings, remove incidental indentation, and still process Java escapes.

## Official reference

- [JEP 378: Text Blocks — JDK 15](https://openjdk.org/jeps/378)
