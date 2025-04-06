import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from dramatiq.results import Results # Import the Results middleware
from dramatiq.results.backends.stub import StubBackend # Import a backend (Stub for now)

# Configure the RabbitMQ broker connection
# Assumes RabbitMQ is running on localhost:5672 with default credentials (guest/guest)
# TODO: Make broker URL configurable (e.g., via environment variables)
rabbitmq_broker = RabbitmqBroker(url="amqp://guest:guest@localhost:5672")
dramatiq.set_broker(rabbitmq_broker)

# Optional: Configure other Dramatiq settings if needed
# dramatiq.set_encoder(...)

# Add the Results middleware with a backend
# Using StubBackend for now; replace with RedisBackend or MemcachedBackend for persistence
results_backend = StubBackend()
rabbitmq_broker.add_middleware(Results(backend=results_backend))
