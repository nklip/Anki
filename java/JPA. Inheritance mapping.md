# Hibernate: Inheritance Mapping

## Front

How does Hibernate map a Java inheritance hierarchy, and when should each inheritance strategy be used?

## Back

Relational databases do not support class inheritance directly. Hibernate maps an entity hierarchy using one of three Jakarta Persistence strategies:

```java
@Inheritance(strategy = InheritanceType.SINGLE_TABLE)
@Inheritance(strategy = InheritanceType.JOINED)
@Inheritance(strategy = InheritanceType.TABLE_PER_CLASS)
```

`@MappedSuperclass` is another way to reuse persistent fields, but it does **not** create a polymorphic entity hierarchy.

### Example hierarchy

```java
@Entity
@Inheritance(strategy = InheritanceType.SINGLE_TABLE)
abstract class Payment {
    @Id
    @GeneratedValue
    private Long id;

    private BigDecimal amount;
}

@Entity
class CardPayment extends Payment {
    private String cardLastFourDigits;
}

@Entity
class BankTransfer extends Payment {
    private String iban;
}
```

The strategy is declared on the root entity and applies to its entity subclasses.

### 1. `SINGLE_TABLE`

All classes in the hierarchy are stored in one table. A discriminator identifies the concrete Java type.

```java
@Entity
@Inheritance(strategy = InheritanceType.SINGLE_TABLE)
@DiscriminatorColumn(name = "payment_type")
abstract class Payment { }

@Entity
@DiscriminatorValue("CARD")
class CardPayment extends Payment { }

@Entity
@DiscriminatorValue("BANK")
class BankTransfer extends Payment { }
```

Simplified schema:

```text
payment
------------------------------------------------------------
id | amount | payment_type | card_last_four_digits | iban
```

#### Advantages

- Usually the fastest polymorphic reads because only one table is scanned.
- No joins are required to load a subclass.
- Simple schema and queries.

#### Disadvantages

- Subclass-specific columns must normally be nullable.
- The table can become wide and sparse with many subclasses.
- Database constraints for subtype-specific fields are harder to express.

If `@Inheritance` is omitted from an entity hierarchy, `SINGLE_TABLE` is the Jakarta Persistence default. Hibernate normally uses a `DTYPE` discriminator column when none is specified.

### 2. `JOINED`

The root class and every subclass have separate tables. A subclass table's primary key is also a foreign key to the parent table.

```java
@Entity
@Inheritance(strategy = InheritanceType.JOINED)
abstract class Payment { }

@Entity
@PrimaryKeyJoinColumn(name = "payment_id")
class CardPayment extends Payment { }
```

Simplified schema:

```text
payment
------------------
id | amount

card_payment
------------------------------------
payment_id (PK, FK) | card_last_four_digits

bank_transfer
---------------------------
payment_id (PK, FK) | iban
```

#### Advantages

- Normalized schema with no unused subclass columns.
- Subclass-specific columns can use `NOT NULL` and other constraints.
- Shared fields exist in one place.

#### Disadvantages

- Loading a subclass requires joining its table with parent tables.
- A polymorphic query may join every subclass table.
- Inserts, updates, and deletes may touch multiple tables.

Use it when data integrity and normalization matter more than minimizing joins.

### 3. `TABLE_PER_CLASS`

Every concrete entity has its own table containing both inherited and subclass-specific fields.

```java
@Entity
@Inheritance(strategy = InheritanceType.TABLE_PER_CLASS)
abstract class Payment { }

@Entity
class CardPayment extends Payment { }

@Entity
class BankTransfer extends Payment { }
```

Simplified schema:

```text
card_payment
--------------------------------------------
id | amount | card_last_four_digits

bank_transfer
------------------
id | amount | iban
```

#### Advantages

- A concrete subtype can be read from one table without joins.
- Each table can enforce constraints for its concrete type.
- No nullable columns belonging to unrelated subclasses.

#### Disadvantages

- Inherited columns are duplicated across tables.
- Schema changes to a base field affect every subclass table.
- Polymorphic queries require `UNION`/`UNION ALL` across the hierarchy and can be expensive.
- Associations to the base type are difficult to enforce with a normal database foreign key.

Use it sparingly, usually only for small hierarchies where queries target concrete types rather than the root type.

### 4. `@MappedSuperclass`

A mapped superclass contributes persistent fields to its subclasses, but it is not an entity and has no table of its own.

```java
@MappedSuperclass
abstract class BaseEntity {
    @Id
    @GeneratedValue
    private Long id;

    private Instant createdAt;
}

@Entity
class Customer extends BaseEntity { }

@Entity
class Product extends BaseEntity { }
```

`Customer` and `Product` are independent entity types. This query is invalid because `BaseEntity` is not an entity:

```java
// Invalid JPQL/HQL
select b from BaseEntity b
```

Use `@MappedSuperclass` for mapping reuse when polymorphic queries and associations to the base type are not needed.

### Polymorphic queries

When the root is an entity, a query against it returns instances of the root and its entity subclasses:

```java
List<Payment> payments = entityManager.createQuery(
        "select p from Payment p",
        Payment.class
).getResultList();
```

The generated SQL depends on the mapping:

- `SINGLE_TABLE` → scan one table and inspect the discriminator.
- `JOINED` → join the root and subclass tables.
- `TABLE_PER_CLASS` → union the tables in the hierarchy.
- `@MappedSuperclass` → no polymorphic query is possible.

### Comparison

| Mapping | Database shape | Polymorphic query | Main trade-off |
|---|---|---|---|
| `SINGLE_TABLE` | One table for the hierarchy | One table scan | Fast, but wide and nullable |
| `JOINED` | Root table plus one table per subclass | Multiple joins | Normalized, but join-heavy |
| `TABLE_PER_CLASS` | One complete table per concrete class | Multiple unions | Independent tables, but duplicated data |
| `@MappedSuperclass` | One table per concrete entity | Not supported | Reuses mappings without entity polymorphism |

### Practical choice

1. Start with `SINGLE_TABLE` for a small, stable hierarchy and frequent polymorphic queries.
2. Choose `JOINED` when subtype constraints and a normalized schema are more important.
3. Consider `TABLE_PER_CLASS` only when concrete-type queries dominate and the hierarchy is small.
4. Use `@MappedSuperclass` when only fields and mappings need to be inherited.
5. Prefer composition or associations when the relationship is not truly an **is-a** relationship.

### Key idea

> `SINGLE_TABLE` avoids joins, `JOINED` preserves normalization, `TABLE_PER_CLASS` duplicates inherited columns, and `@MappedSuperclass` provides reuse without polymorphism.

### Official reference

- [Hibernate ORM User Guide: Inheritance](https://docs.hibernate.org/orm/current/userguide/html_single/#entity-inheritance)
