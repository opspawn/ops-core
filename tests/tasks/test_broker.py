import pytest
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from dramatiq.results import Results
from dramatiq.results.backends.stub import StubBackend

# Import the instance directly from the module
from ops_core.tasks.broker import rabbitmq_broker


def test_broker_instance_created():
    """
    Test that the rabbitmq_broker instance is created and configured correctly.
    """
    assert isinstance(rabbitmq_broker, RabbitmqBroker)
    # Note: The URL is currently hardcoded in broker.py.
    # Testing the exact URL value here is brittle if the implementation changes
    # or if middleware structure makes accessing it difficult.
    # We will focus on ensuring the broker is the correct type and
    # has the essential Results middleware configured.

    # Check if the Results middleware was added
    assert len(rabbitmq_broker.middleware) > 0, "Broker should have middleware"
    results_middleware_found = False
    for mw in rabbitmq_broker.middleware:
        if isinstance(mw, Results):
            results_middleware_found = True
            # Check if the correct backend (StubBackend for now) is configured
            assert isinstance(mw.backend, StubBackend)
            break
    assert results_middleware_found, "Results middleware not found on the broker"
