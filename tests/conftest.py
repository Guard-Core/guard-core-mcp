import sys
from collections.abc import Iterator

import network_guard
import pytest
import thread_guard

network_guard.install()
thread_guard.install()


@pytest.fixture(autouse=True)
def _no_outbound_network() -> Iterator[None]:
    network_guard.reset()
    yield
    violations = network_guard.drain()
    assert not violations, "test reached the network:\n" + "\n".join(violations)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    thread_guard.stop_the_shared_regex_pools()
    leaked = thread_guard.leaked_threads()
    if leaked:
        sys.stderr.write(f"\nthreads the tests left running: {leaked}\n")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
