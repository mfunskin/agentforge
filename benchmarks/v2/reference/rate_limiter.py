"""Token-bucket admission with an injectable monotonic clock."""


class TokenBucket:
    def __init__(self, capacity, refill_rate, clock):
        if capacity <= 0 or refill_rate < 0:
            raise ValueError("capacity must be positive and refill rate nonnegative")
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.clock = clock
        self.tokens = float(capacity)
        self.updated_at = clock()

    def allow(self, amount=1):
        if amount <= 0 or amount > self.capacity:
            raise ValueError("invalid token amount")
        now = self.clock()
        if now > self.updated_at:
            self.tokens = min(
                self.capacity,
                self.tokens + (now - self.updated_at) * self.refill_rate,
            )
            self.updated_at = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False
