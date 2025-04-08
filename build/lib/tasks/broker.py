import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from dramatiq.middleware import AsyncIO # Import AsyncIO middleware
from dramatiq.results import Results # Import the Results middleware
from dramatiq.results.backends.stub import StubBackend # Import a backend (Stub for now)

# Configure the RabbitMQ broker connection
# Assumes RabbitMQ is running on localhost:5672 with default credentials (guest/guest)
# TODO: Make broker URL configurable (e.g., via environment variables)
# Added declare_queue=True to ensure the default queue exists (Removed - Invalid argument)
# Removed explicit url, relying on defaults (amqp://guest:guest@localhost:5672)
rabbitmq_broker = RabbitmqBroker()
dramatiq.set_broker(rabbitmq_broker)
rabbitmq_broker.declare_queue("default") # Explicitly declare the default queue

# Optional: Configure other Dramatiq settings if needed
# dramatiq.set_encoder(...)

# Add the Results middleware with a backend
# Using StubBackend for now; replace with RedisBackend or MemcachedBackend for persistence
results_backend = StubBackend()
rabbitmq_broker.add_middleware(Results(backend=results_backend))
rabbitmq_broker.add_middleware(AsyncIO()) # Add the AsyncIO middleware
