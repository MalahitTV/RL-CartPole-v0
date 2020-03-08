from collections import deque
import random
import numpy as np
import pandas as pd
import torch
from torch.nn import functional as F
import matplotlib.pyplot as plt

from IPython.display import clear_output

device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

moving_average = lambda x, **kw: pd.DataFrame({'x':np.asarray(x)}).x.ewm(**kw).mean().values

class DQNAgent:
    def __init__(self, model, optimizer, loss_func, action_space, memory, gamma=0.99, epsilon=0.1):
        self.model = model
        self.optimizer = optimizer
        self.loss_func = loss_func
        self.target_model = model
        self.action_space = action_space
        self.memory = deque(maxlen=memory)
        self.gamma = torch.Tensor([gamma]).to(device)
        self.epsilon = epsilon

    def fit(self, env, steps, batch_size=200, train_every=10, batch_count=1):
        rewards_history = []
        for step in range(steps):
            state = env.reset()
            done = False
            rewards = 0
            while not done:
                action = self.policy(state)
                next_state, reward, done, _ = env.step(action)
                rewards += reward
                self.memory.append((state, action, reward, next_state, done))
                state = next_state
            rewards_history.append(rewards)

            if len(self.memory) > batch_size:
                for _ in range(batch_count):
                    batch = random.sample(self.memory, batch_size)
                    self.train(batch)
            else:
                batch = self.memory
                self.train(batch)

            if step % 10:
                clear_output(True)
                plt.figure(figsize=[12, 6])
                plt.title('Returns');
                plt.grid()
                plt.scatter(np.arange(len(rewards_history)), rewards_history, alpha=0.1)
                plt.plot(moving_average(rewards_history, span=10, min_periods=10))
                plt.show()

            if step % train_every:
                self.target_model.set_parameters(self.model.get_parameters())

    def train(self, batch):
        state0_batch = []
        state1_batch = []
        reward_batch = []
        action_batch = []
        terminal1_batch = []
        for state0, action, reward, state1, terminal1 in batch:
            state0_batch.append(state0)
            state1_batch.append(state1)
            reward_batch.append(reward)
            action_batch.append(action)
            terminal1_batch.append(0. if terminal1 else 1.)

        state0_batch = torch.FloatTensor(state0_batch).to(device)
        state1_batch = torch.FloatTensor(state1_batch).to(device)
        reward_batch = torch.FloatTensor(reward_batch).to(device)
        # terminal1_batch = torch.Tensor(terminal1_batch).to(device)
        target_q_values1 = self.target_model(state1_batch).detach()

        q_values1, _ = torch.max(target_q_values1, dim=1)

        discounted_reward_batch = self.gamma * q_values1
        # discounted_reward_batch *= terminal1_batch
        rs = reward_batch + discounted_reward_batch

        q_values0 = self.model(state0_batch)
        # max_q_values0, _ = torch.max(q_values0, dim=1)
        loss = self.loss_func(rs.reshape(-1, 1), q_values0)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

    def policy(self, state):
        if random.random() <= self.epsilon:
            return random.randint(0, self.action_space - 1)
        else:
            return torch.argmax(F.softmax(self.model(torch.FloatTensor(state).to(device))), dim=-1).detach().cpu().numpy()