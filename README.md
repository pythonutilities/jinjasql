This is a forked version of [jinjasql](https://github.com/sripathikrishnan/jinjasql), maintained at [pythonutilities/jinjasql](https://github.com/pythonutilities/jinjasql) and published on PyPI as [jinjasql2](https://pypi.org/project/jinjasql2/).

# Generate SQL Queries using a Jinja Template, without worrying about SQL Injection #

[![Github Actions Build Status](https://github.com/pythonutilities/jinjasql/workflows/Tests/badge.svg)](https://github.com/pythonutilities/jinjasql/actions)

JinjaSQL is a template language for SQL statements and scripts.
Since it's based in [Jinja2](https://jinja.palletsprojects.com/),
you have all the power it offers - conditional statements, macros,
looping constructs, blocks, inheritance, and many more.

JinjaSQL automatically binds parameters that are inserted into the template.
After JinjaSQL evaluates the template, you get:

1. A query with placeholders for the parameters
2. The values corresponding to the placeholders that need to be bound to the query

JinjaSQL doesn't actually execute the query - it only prepares the
query and the bind parameters. You can execute the query using any
database engine / driver you are working with.

For example, if you have a template like this -

```sql
select username, sum(spend)
from transactions
where start_date > {{request.start_date}}
and end_date < {{request.end_date}}
{% if request.organization %}
and organization = {{request.organization}}
{% endif %}
```

then, depending on the parameters you provide, you get a query
(shown here with `param_style='format'`; the default `named` style
is covered below)

```sql
select username, sum(spend)
from transaction
where start_date > %s
and end_date < %s
and organization = %s
```
with bind parameters `('2016-10-10', '2016-10-20', 1321)`.

If `request.organization` was empty/falsy, the corresponding and clause
would be absent from the query, and the bind parameters
would not have the organization id.

## When to use JinjaSQL ##

JinjaSQL is *not* meant to replace your ORM. ORMs like those provided
by SQLAlchemy or Django are great for a variety of use cases, and should
be the default in most cases. But there are a few use cases where
you really need the power of SQL.

Use JinjaSQL for -

1. Reporting, business intelligence or dashboard like use cases
1. When you need aggregation/group by
1. Use cases that require data from multiple tables
1. Migration scripts & bulk updates that would benefit from macros

In all other use cases, you should reach to your ORM
instead of writing SQL/JinjaSQL.

While JinjaSQL can handle insert/update statements, you are better off
using your ORM to handle such statements. JinjaSQL is mostly meant
for dynamic select statements that an ORM cannot handle as well.

**A note on trust:** JinjaSQL protects you from SQL injection through
*values* - anything a `{{ variable }}` produces is bound, never inlined.
The templates themselves must still be trusted: they are ordinary Jinja
templates (evaluated without a sandbox) and the `| sqlsafe` filter lets a
template inline anything verbatim. Treat templates as code written by
developers, and context data as untrusted input.

## Basic Usage ##

First, import the `JinjaSql` class and create an object. `JinjaSql` is thread-safe, so you can safely create one object at startup and use it everywhere. Just don't share the same Jinja `Environment` object across multiple `JinjaSql` instances - each instance configures the environment it is given.

```python
from jinjasql import JinjaSql
j = JinjaSql()
```

Next, create your template query. You can use the full power of Jinja templates over here - macros, includes, imports, if/else conditions, loops, filters and so on. You can load the template from a file or from database or wherever else Jinja supports.

```python
template = """
    SELECT project, timesheet, hours
    FROM timesheet
    WHERE user_id = {{ user_id }}
    {% if project_id %}
    AND project_id = {{ project_id }}
    {% endif %}
"""
```

Create a context object. This object is a regular dictionary, and can contain nested dictionaries, lists or objects. The template query is evaluated against this context object.

```python
data = {
    "project_id": 123,
    "user_id": "sripathi"
}
```

Finally, call the `prepare_query` method with the template and the context. You get back two things:

1. `query` is the generated SQL query. With the default `param_style='named'`, variables are replaced by `:name` style placeholders
1. `bind_params` is a dictionary of parameters corresponding to the placeholders

```python
query, bind_params = j.prepare_query(template, data)
```

This is the query that is generated:

```python
expected_query = """
    SELECT project, timesheet, hours
    FROM timesheet
    WHERE user_id = :user_id_1

    AND project_id = :project_id_2
"""
```

And these are the bind parameters:

```python
self.assertEqual(bind_params, {"user_id_1": "sripathi", "project_id_2": 123})
self.assertEqual(query.strip(), expected_query.strip())
```

You can now use the query and bind parameters to execute the query. For example, in django, you would do something like this:

```python
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute(query, bind_params)
    for row in cursor.fetchall():
        # do something with the results
        pass
```

## Multiple Param Styles ##
Per [PEP-249](https://www.python.org/dev/peps/pep-0249/), bind parameters can be specified in multiple ways.
You can pass the optional constructor argument `param_style` to control
the style of query parameter.

1. **format** : `... where name = %s`
1. **qmark** :  `where name = ?`
1. **numeric** : `where name = :1 and last_name = :2`
1. **named** : `where name = :name and last_name = :last_name`. This is the default.
1. **pyformat** : `where name = %(name)s and last_name = %(last_name)s`
1. **asyncpg** : `where name = $1 and last_name = $2`. This is not part of PEP-249 standard, but is used by [asyncpg library for postgres](https://magicstack.github.io/asyncpg/current/usage.html)

Here's how it works -

```python
j = JinjaSql(param_style='named')
query, bind_params = j.prepare_query(template, data)
```

If param_style is `named` or `pyformat`, `bind_params` will be a python dictionary. For all other param styles, it will be a tuple.

In case of `named` and `pyformat`, remember the following:

1. `prepare_query` returns a dictionary instead of a tuple
1. The returned dictionary is flat, and only contains keys that are actually used in the query
1. The keys in the dictionary and in the query are guaranteed to have unique names. Even if you bind the same parameter twice, the key will be renamed

## Handling In Clauses ##
For SQL `in` clauses, you have to apply the `| inclause` filter, so that
JinjaSQL creates one bind expression per element:

```sql
select 'x' from dual
where project_id in {{ project_ids | inclause }}
```
Notice that you don't need to enclose in parantheses.

The `inclause` filter expects a non-empty list or tuple; it raises a
`ValueError` for an empty sequence (which would generate invalid SQL)
or a plain string (which would bind one parameter per character).

Without the filter, a list or tuple is bound as a *single* parameter.
That is intentional - drivers like psycopg2 and asyncpg accept python
lists for postgres array columns (e.g. `WHERE {{some_num}} = ANY({{some_array}})`) -
but it will not work as an `in` clause.

## SQL Safe Strings ##
Sometimes, you want to insert dynamic table names/column names. By default, JinjaSQL will convert them to bind parameters. This won't work, because table and column names are usually not allowed in bind
parameters.

In such cases, you can use the `|sqlsafe` filter.

```sql
select {{column_names | sqlsafe}} from dual
```

If you use `sqlsafe`, it is your responsibility to ensure there is no sql injection.

Alternatively, the `|identifier` filter can be used to produce escaped strings for safe usage of SQL identifiers such as table or column names. Pass a string for a plain identifier, or a tuple for a qualified one (e.g. schema and table):

```python
template = """
select {{column1 | identifier}}, {{column2 | identifier}} from {{source | identifier}}
"""
j = JinjaSql()
query, bind_params = j.prepare_query(
    template, {'column1': 'col1', 'column2': 'col2', 'source': ('a_schema', 'a_table')}
)
```

Would result in the following query being rendered:

```sql
select "col1", "col2" from "a_schema"."a_table"
```

Identifiers are quoted with double quotes by default (ANSI SQL, postgres).
For databases like MySQL that quote identifiers with backticks, use the
optional constructor argument `identifier_quote_character`:

```python
j = JinjaSql(identifier_quote_character='`')
```

## Installing jinjasql ##

Pre-Requisites :

1. python >= 3.8
2. jinja2 >= 3.1.6 (installed automatically as a dependency)

To install from PyPi (recommended) :

    pip install jinjasql2

Note: the package is published as `jinjasql2`, but it installs the
`jinjasql` python module - don't install it side-by-side with the
original `jinjasql` package.

## How does JinjaSQL work? ##

### The bind filter ###

At it's core, JinjaSQL provides a filter called `bind`. This filter gobbles up whatever value is provided, and emits a placeholder in its place. The actual value is then stored in a thread local list of bind parameters.

```python
jinja.prepare_query("select * from user where id = {{userid | bind}}",
                    {"userid": 143})
```

When this code is evaluated, the output query is `select * from user where id = %s` (with `param_style='format'`).

### Pre-processing the Query Template ###

Manually applying the `bind` filter to every parameter is error-prone. Sooner than later, a developer will miss the filter, and it will lead to SQL Injection.

JinjaSQL automatically applies the bind filter to ALL variables. The query template is transformed before it is evaluated.

```sql
select * from user where id = {{userid}}
```

becomes

```sql
select * from user where id = {{userid | bind}}
```

Jinja lets extensions [rewrite the token stream](https://jinja.palletsprojects.com/en/stable/extensions/#jinja2.ext.Extension.filter_stream). JinjaSQL looks for `variable_begin` and `variable_end` tokens in the stream, and rewrites the stream to include the `bind` filter as the last filter.

### Autoescape and JinjaSQL ###

Jinja has an autoescape feature. If turned on, it automatically HTML escapes variables. It does this by wrapping strings using the `Markup` class.

JinjaSQL builds on this functionality. JinjaSQL requires autoescape to be turned on. As a result, strings that are injected are wrapped using the Markup class. JinjaSQL uses this wrapper class as well to prevent double-binding of parameters.

## License

jinjasql is licensed under the MIT License. See [LICENSE](LICENSE).

## Copyright

(c) 2016 HashedIn Technologies Pvt. Ltd.
(c) 2021 Sripathi Krishnan
