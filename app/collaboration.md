# SQL Injection Prevention Guide

## Safe Patterns

- Always use SQLAlchemy ORM for database operations:
  ```python
  # Good: Using SQLAlchemy ORM
  user = User.query.filter_by(username=username).first()

When using filters with user input, use parameter binding:
python# Good: Parameters are safely bound
db.session.query(User).filter(User.username == username)

For raw SQL, use parameterized queries:
``` python# Good: Parameters are safely bound
db.session.execute(text("SELECT * FROM users WHERE username = :username"), 
                   {"username": username})
```

### Unsafe Patterns to Avoid

Never use string formatting or concatenation in SQL:
python# BAD: SQL Injection vulnerability
query = f"SELECT * FROM users WHERE username = '{username}'"
db.engine.execute(query)

Don't build SQL queries with user input:
python# BAD: SQL Injection vulnerability
order_by = request.args.get('sort_by')
query = f"SELECT * FROM products ORDER BY {order_by}"


### Best Practices

Use the application's safe_query and execute_raw_sql helper functions
Always validate and sanitize user input
Use SQLAlchemy ORM whenever possible
Apply the principle of least privilege to database users
Regular security audits of database code

# Security Review Process

### Database Operations
- All new code that interacts with the database must be reviewed for SQL injection vulnerabilities
- Use the provided helper functions for database access
- No direct string concatenation in SQL queries
- All raw SQL must use parameterized queries

### Code Review Checklist
- [ ] Database queries use SQLAlchemy ORM or parameterized queries
- [ ] No string formatting or concatenation in SQL statements
- [ ] Input validation for all user-supplied data
- [ ] Error handling that doesn't expose database details