import numpy as np
import torch
from torch import nn


class WorldModel(nn.Module):
    def __init__(self, inputs, hidden=48, embedding=8):
        super().__init__()
        self.initial = nn.Linear(inputs, hidden)
        self.embedding = nn.Embedding(6, embedding)
        self.gru = nn.GRU(embedding, hidden, batch_first=True)
        self.output = nn.Linear(hidden, 5)

    def forward(self, context, tokens):
        h = torch.tanh(self.initial(context)).unsqueeze(0)
        z, _ = self.gru(self.embedding(tokens), h)
        return self.output(z)


class Source:
    """One call row includes recurrent update AND next-symbol distribution."""
    def __init__(self, checkpoint, context):
        self.model = WorldModel(checkpoint['inputs'])
        self.model.load_state_dict(checkpoint['state'])
        self.model.eval()
        x = np.nan_to_num((context-checkpoint['mean'])/checkpoint['scale'], nan=0.0)
        x = np.clip(x, -10, 10).astype(np.float32)
        with torch.no_grad():
            self.initial = torch.tanh(self.model.initial(torch.tensor(x))).numpy()
        self.rows = 0

    def evaluate(self, h, last):
        self.rows += len(last)
        with torch.no_grad():
            h = torch.as_tensor(np.asarray(h), dtype=torch.float32).unsqueeze(0)
            a = torch.as_tensor(last, dtype=torch.long).reshape(-1, 1)
            z, _ = self.model.gru(self.model.embedding(a), h)
            p = torch.softmax(self.model.output(z[:, 0]).double(), dim=-1)
            return z[:, 0].numpy(), p.numpy()
