# OpenBuild API Reference

Base URL: `http://localhost:3000/api`

## Authentication

### POST /auth/register
Create a new user account and organization.

**Request:**
```json
{
  "email": "user@example.com",
  "name": "John Smith",
  "password": "secure-password"
}
```

### POST /auth/login
Authenticate and receive a JWT token.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secure-password"
}
```

**Response:**
```json
{
  "token": "eyJ...",
  "user": { "id": "uuid", "email": "...", "name": "...", "role": "admin" }
}
```

## Projects

### GET /projects
List all projects for the current organization.

### POST /projects
Create a new project.

**Request:**
```json
{
  "name": "Office Building Renovation",
  "number": "2024-001",
  "address": "123 Main St, Springfield"
}
```

### GET /projects/:id
Get project details.

### PUT /projects/:id
Update project fields.

### DELETE /projects/:id
Soft-delete a project.

## Drawing Sets

### GET /projects/:project_id/drawing-sets
List drawing sets for a project.

### POST /projects/:project_id/drawing-sets
Upload a new drawing set (multipart/form-data with PDF file).

### GET /projects/:project_id/drawing-sets/:id
Get drawing set details including sheet list.

## Takeoff

### GET /drawing-sets/:id/layers
List takeoff layers for a drawing set.

### POST /drawing-sets/:id/layers
Create a new takeoff layer.

**Request:**
```json
{
  "name": "Concrete",
  "color": "#3b82f6",
  "cost_code": "03"
}
```

### GET /layers/:layer_id/measurements
List measurements for a layer.

### POST /layers/:layer_id/measurements
Create a new measurement.

**Request:**
```json
{
  "sheet_id": "uuid",
  "measurement_type": "area",
  "points": [{"x": 100, "y": 200}, {"x": 300, "y": 200}, {"x": 300, "y": 400}, {"x": 100, "y": 400}],
  "value": 450.5,
  "unit": "SF",
  "cost_code": "09 30 00",
  "label": "Floor tile - Lobby"
}
```

## Estimates

### GET /projects/:project_id/estimates
List estimates for a project.

### POST /projects/:project_id/estimates
Create a new estimate.

### GET /estimates/:estimate_id
Get estimate details.

### GET /estimates/:estimate_id/line-items
List line items for an estimate.

### POST /estimates/:estimate_id/line-items
Add a line item to an estimate.

**Request:**
```json
{
  "cost_code": "09 30 00",
  "description": "Ceramic floor tile - lobby area",
  "quantity": 450.5,
  "unit": "SF",
  "unit_cost_cents": 1200,
  "measurement_id": "uuid (optional)"
}
```

### PUT /line-items/:item_id
Update a line item.

### DELETE /line-items/:item_id
Delete a line item.

## Error Responses

All errors follow this format:
```json
{
  "code": "NOT_FOUND",
  "message": "Project not found",
  "details": {}
}
```

Common error codes:
- `VALIDATION_ERROR` — Invalid request body
- `NOT_FOUND` — Resource doesn't exist
- `UNAUTHORIZED` — Missing or invalid auth token
- `FORBIDDEN` — Insufficient permissions
- `CONFLICT` — Resource already exists
