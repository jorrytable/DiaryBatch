from dataclasses import dataclass, asdict

@dataclass
class ReviewItem:
    id: str
    review_date: str
    title: str
    url: str
    genre: str
    impression: str

    def to_dict(self):
        return asdict(self)