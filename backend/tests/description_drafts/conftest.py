import pytest


class DescriptionGateway:
    def __init__(self):
        self.output = {"description": "A sourdough loaf, sold by the loaf."}
        self.calls = []
        self.after = None
        self.error = None

    def complete(self, messages, schema):
        self.calls.append({"messages": messages, "schema": schema})
        if self.after:
            self.after()
        if self.error:
            raise self.error
        return self.output


@pytest.fixture
def description_gateway(market_client):
    gateway = DescriptionGateway()
    market_client.app.state.assistant_gateway = gateway
    return gateway


@pytest.fixture
def description_path(market_record):
    return market_record["path"] + "/description-drafts"
