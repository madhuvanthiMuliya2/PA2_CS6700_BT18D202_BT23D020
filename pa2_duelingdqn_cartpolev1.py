# -*- coding: utf-8 -*-
"""DuelingDQN-Cartpolev1.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/19sB-P9obPEuQyuZX_6trPO2_xns5n5JR
"""

# Importing libraries
import gym
import tensorflow as tf
import numpy as np
import tqdm
import random
import sys
from scipy.special import softmax
from collections import namedtuple, deque
import matplotlib.pyplot as plt
import pickle

# Network hyperparameters
# Type 1
t1_units = [256,256,256]
# Type 2
t2_units = [64,64,64]

value_units = 1
adv_units = 2

# Dueling DQN Type 1

class DuelDQNettype1(tf.keras.Model):
  def __init__(self):
    super(DuelDQNettype1, self).__init__()

    self.dense1 = tf.keras.layers.Dense(t1_units[0], activation = tf.nn.relu)
    self.dense2 = tf.keras.layers.Dense(t1_units[1], activation = tf.nn.relu)
    self.dense3 = tf.keras.layers.Dense(t1_units[2], activation = tf.nn.relu)
    self.value_layer= tf.keras.layers.Dense(value_units)
    self.advantage_layer = tf.keras.layers.Dense(adv_units)

  def call(self,inp):

    d1 = self.dense1(inp)
    v1 = self.dense2(d1)
    a1 = self.dense3(d1)

    value = self.value_layer(v1)
    advantage = self.advantage_layer(a1)

    # Type 1
    aggregate = tf.reduce_mean(advantage, 1, True)

    Q = value + (advantage - aggregate)

    return Q

  def choose_action(self, state, num_actions, tau):
    Q = self.call(tf.expand_dims(state, axis=0))
    Q_vals = tf.reshape(Q, [num_actions,])
    probs = softmax(Q_vals/tau)
    act = np.random.choice(num_actions, 1, p=probs)[0]
    return act

# Dueling DQN Type 2

class DuelDQNettype2(tf.keras.Model):
  def __init__(self):
    super(DuelDQNettype2, self).__init__()

    self.dense1 = tf.keras.layers.Dense(t2_units[0], activation = tf.nn.relu)
    self.dense2 = tf.keras.layers.Dense(t2_units[1], activation = tf.nn.relu)
    self.dense3 = tf.keras.layers.Dense(t2_units[2], activation = tf.nn.relu)
    self.value_layer= tf.keras.layers.Dense(value_units)
    self.advantage_layer = tf.keras.layers.Dense(adv_units)

  def call(self,inp):

    d1 = self.dense1(inp)
    v1 = self.dense2(d1)
    a1 = self.dense3(d1)

    value = self.value_layer(v1)
    advantage = self.advantage_layer(a1)

    # Type 2
    aggregate = tf.math.reduce_max(advantage)
    aggregate = tf.cast(tf.reshape(tf.argmax(advantage, 1), [len(advantage), 1]), tf.float64)

    Q = value + (advantage - aggregate)

    return Q

  def choose_action(self, state, num_actions, tau):
    Q = self.call(tf.expand_dims(state, axis=0))
    Q_vals = tf.reshape(Q, [num_actions,])
    probs = softmax(Q_vals/tau)
    act = np.random.choice(num_actions, 1, p=probs)[0]
    return act

class MemoryBuffer():
  def __init__(self,memory_size):
    self.memory_size = memory_size
    self.mem = deque(maxlen = memory_size)

  def record(self, experience_tuple):
    self.mem.append(experience_tuple)

  def size(self):
    return len(self.mem)

  def sample(self,batch_size):
    if batch_size > len(self.mem):
      batch_size = len(self.mem)
    idx = np.random.choice(np.arange(len(self.mem)),size=batch_size,replace=False)
    batch_mem = [self.mem[i] for i in idx]
    return batch_mem

class DuelingDQN():
    def __init__(self, type_ddqn):
        # Creating environment
        self.env = gym.make('CartPole-v1')

        # Environment parameters
        self.num_actions = self.env.action_space.n
        self.state_size = self.env.observation_space.shape[0]

        # Initializing networks and optimizers based on Type 1 or Type
        self.type = type_ddqn
        if self.type == 1:
            self.ddqn = DuelDQNettype1()
            self.ddqn_tgt = DuelDQNettype1()
        if self.type == 2:
            self.ddqn = DuelDQNettype2()
            self.ddqn_tgt = DuelDQNettype2()
        self.optimizer = tf.keras.optimizers.Adam(learning_rate)
        self.loss_fn = tf.keras.losses.MeanSquaredError()

        # Setting target network weights to learning network's weights
        self.ddqn_tgt.set_weights(self.ddqn.get_weights())

        self.memory = MemoryBuffer(mem_size)


    def train_net(self, states, actions, rewards, next_states, dones):
        # Optimizing dueling dqn learning network
        next_act_l = tf.cast(tf.argmax(self.ddqn(next_states), 1), tf.int32)
        next_act_l_idx = tf.stack([tf.range(tf.shape(next_act_l)[0]), next_act_l], 1)
        q_tgt = self.ddqn_tgt(next_states)
        Q_target = rewards + (1 - dones) * gamma * tf.stop_gradient(tf.gather_nd(q_tgt, next_act_l_idx))

        with tf.GradientTape() as tape:
            act_l = tf.cast(actions, tf.int32)
            act_l_idx = tf.stack([tf.range(tf.shape(act_l)[0]), act_l], 1)
            q_l = self.ddqn(states)
            Q_pred = tf.gather_nd(q_l, act_l_idx)
            loss = self.loss_fn(Q_pred, Q_target)

        grad = tape.gradient(loss, self.ddqn.trainable_variables)
        self.optimizer.apply_gradients(zip(grad, self.ddqn.trainable_variables))


    def update_target(self):
        self.ddqn_tgt.set_weights(self.ddqn.get_weights())


    def train(self):
        tf.keras.backend.set_floatx('float64')
        running_reward = 10
        avg_running_reward = []
        episode_rewards_total = []

        state = self.env.reset()
        train_step = 0
        tau = tau_initial

        for ep in range(num_episodes):
            ep_reward = 0

            for iter in range(iterations):
                # Softmax
                action = self.ddqn.choose_action(state, self.num_actions, tau)
                next_state,reward,done,_ = self.env.step(action) # sending action to environment
                ep_reward += reward
                # Recording experience
                self.memory.record((state, action, reward, next_state, done))

                if self.memory.size() > batch_size:
                    # Training learning network
                    train_step += 1
                    if  train_step % update_tgtstep == 0:
                        # Updating target network weights
                        self.update_target()

                    # Sampling experience
                    batch = self.memory.sample(batch_size)
                    states, actions, rewards, next_states, dones = zip(*batch)

                    # Computing loss, gradients and training learning network
                    loss = self.train_net(np.asarray(states), np.asarray(actions), np.asarray(rewards), np.asarray(next_states), np.asarray(dones))

                tau = max(tau_final, tau_decay*tau)
                if done:
                  break
                state = next_state

            # Calculating running reward
            running_reward = 0.05 * ep_reward + (1 - 0.05) * running_reward

            if running_reward > self.env.spec.reward_threshold:
                print(f"Solved! Running reward is now {ep_reward} and the last episode runs to {iter} time steps!")
                # break
            if ep % 100 == 0:
                print(f"Episode {ep}: Reward = {ep_reward} | Avg Reward = {running_reward}")
            avg_running_reward.append(running_reward)
            episode_rewards_total.append(ep_reward)

        return avg_running_reward, episode_rewards_total

# Model hyperparameters
gamma = 0.99
learning_rate = 0.001
num_episodes = 2
iterations = 500
update_tgtstep = 4
mem_size = 50_000
batch_size = 16

# Softmax
tau_decay = 0.995
tau_initial = 0.8
tau_final = 0.001

# Training Dueling DQN models over 5 runs to account for stochasticity
num_runs = 5

reward_over_runs_t1 = []
reward_over_runs_t2 = []
for r in range(num_runs):
    # Creating model of Type 1 eqn
    type_ddqn = 1
    model_t1 = DuelingDQN(type_ddqn)
    # Training model of Type 1 eqn
    rewards_t1, re_ep_t1 = model_t1.train()
    reward_over_runs_t1.append(rewards_t1)

    # Creating model of Type 2 eqn
    type_ddqn = 2
    model_t2 = DuelingDQN(type_ddqn)
    # Training model of Type 2 eqn
    rewards_t2, re_ep_t2 = model_t2.train()
    reward_over_runs_t2.append(rewards_t2)

returns_t1_arr = np.asarray(reward_over_runs_t1)
returns_t2_arr = np.asarray(reward_over_runs_t2)

# Computing mean over 5 runs across 500 episodes
mean_return_t1 = np.mean(returns_t1_arr, axis=0)
mean_return_t2 = np.mean(returns_t2_arr, axis=0)

# Computing standard deviation over 5 runs across 500 episodes
std_return_t1 = np.std(returns_t1_arr, axis=0)
std_return_t2 = np.std(returns_t2_arr, axis=0)

# Comparison by plotting
plt.figure()
plt.plot(mean_return_t1, c='r', label='Type 1')
plt.fill_between(np.arange(0,num_episodes), mean_return_t1+ std_return_t1, mean_return_t1 - std_return_t1, alpha=0.2)
plt.plot(mean_return_t2, c='b', label='Type 2')
plt.fill_between(np.arange(0,num_episodes), mean_return_t2+ std_return_t2, mean_return_t2 - std_return_t2, alpha=0.2)
plt.xlabel('Episode Number')
plt.ylabel('Episodic Return')
plt.title(f'Dueling DQN (CartPole v1)')
plt.legend()
plt.show()