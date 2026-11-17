import torch.nn as nn

# SET CLASS WITH OWN FUNCTIONS TO BE CALLED LATER
class LSTMModel(nn.Module):
    # SETS THE DIMENSIONS TO BE USED IN THE LSTM
    def __init__(self, input_dim, hidden_dim, layer_dim, dropout=0.3):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, layer_dim, batch_first=True)
        self.drop = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_dim, 1)
    #    
    def forward(self, x):        
        out, _ = self.lstm(x)
        return self.fc(self.drop(out[:, -1, :])).squeeze(-1)