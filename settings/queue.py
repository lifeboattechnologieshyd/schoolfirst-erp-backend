from shared.utils import get_from_env

#####################################
#       Message Broker Settings      #
#####################################

BROKER_ENGINE = get_from_env("BROKER_ENGINE", "rabbitmq")  # Options: 'servicebus' or 'rabbitmq'

# RabbitMQ Settings
RABBITMQ_HOST = get_from_env("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = get_from_env("RABBITMQ_PORT", 5672, type_cast=int)
RABBITMQ_VHOST = get_from_env("RABBITMQ_VHOST", "/")
RABBITMQ_USERNAME = get_from_env("RABBITMQ_USERNAME", "guest")
RABBITMQ_PASSWORD = get_from_env("RABBITMQ_PASSWORD", "guest")
RABBITMQ_QUEUE = get_from_env("RABBITMQ_QUEUE", "samsr-queue")
RABBITMQ_CONNECTION_STRING = get_from_env("RABBITMQ_CONNECTION_STRING", None, optional=True)
