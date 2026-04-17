---
name: memory
description: Manage memory operations using Mem0 and MemPalace. Use when users ask to store memories, recall past conversations, manage memory hierarchies, or perform memory palace operations for enhanced recall.
---

# Memory Skill

An expert agent for managing persistent memory operations using Mem0 and MemPalace frameworks.

## Capabilities

- **Mem0 Integration**: Store, retrieve, and manage conversational memories
- **Memory Operations**: Add, update, delete, and search memories
- **MemPalace Organization**: Create memory palaces with hierarchical structure
- **Context Retrieval**: Recall relevant memories based on queries
- **Memory Analytics**: Analyze memory usage patterns and statistics
- **Cross-Session Memory**: Maintain context across multiple conversations

## Mem0 Operations

### Store Memory
```python
# Store a memory with Mem0
memory_client.add(
    content="User prefers dark mode for their IDE",
    user_id="user_123",
    metadata={"source": "conversation", "timestamp": "2024-01-15"}
)
```

### Retrieve Memory
```python
# Search memories
results = memory_client.search(
    query="IDE preferences",
    user_id="user_123",
    limit=5
)
```

### Memory Management
- List all memories for a user
- Update existing memory entries
- Delete memories by ID or filter
- Archive old memories

## MemPalace Operations

### Create Memory Palace
```python
# Create a structured memory palace
palace = memory_client.create_palace(
    name="Project Alpha",
    rooms=["planning", "development", "testing", "deployment"],
    user_id="user_123"
)
```

### Add to Palace Room
```python
# Add memory to specific room
memory_client.add_to_palace(
    palace_id="palace_123",
    room="development",
    content="API endpoint returns 500 on Fridays",
    tags=["bug", "api", "urgent"]
)
```

### Recall from Palace
```python
# Recall using spatial memory technique
memories = memory_client.recall_from_palace(
    palace_id="palace_123",
    query="Friday issues",
    rooms=["development", "testing"]
)
```

## Workflow

### Step 1: Identify Memory Need

1. Determine if this is a store or retrieval operation
2. Identify user context and session ID
3. Check for existing palace structure

### Step 2: Execute Operation

| Operation | Use Case |
|-----------|----------|
| `add` | Store new information |
| `search` | Find related memories |
| `update` | Modify existing memory |
| `delete` | Remove outdated data |
| `palace.add` | Add to memory palace |
| `palace.recall` | Retrieve from palace |

### Step 3: Process Results

1. Parse retrieved memories
2. Filter by relevance and recency
3. Format for context injection

### Step 4: Store Confirmation (if applicable)

1. Confirm successful storage
2. Return memory ID for reference

## Configuration

```json
{
  "mem0_provider": "local|cloud",
  "embedding_model": "text-embedding-3-small",
  "memory_retention_days": 90,
  "palace_max_rooms": 10
}
```

## Output Format

Provide:
1. Operation performed (store/retrieve/update/delete)
2. Memory IDs affected
3. Retrieved content with relevance scores
4. Palace structure updates (if applicable)
