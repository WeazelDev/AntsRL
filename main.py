import pickle
from tqdm import tqdm
import datetime
import time
import math

from gui.visualize import Visualizer

from environment.RL_api import RLApi
from generator.environment_generator import EnvironmentGenerator
from generator.map_generators import *
from agents.random_agent import RandomAgent
from environment.rewards.reward_custom import *

from agents.explore_agent_pytorch import ExploreAgentPytorch
# from agents.explore_agent import ExploreAgent
from agents.collect_agent_rework import CollectAgentRework
from agents.collect_agent_memory import CollectAgentMemory


# -------------------------------------------
#               Main parameters
# -------------------------------------------
aggregate_stats_every = 5
save_model = True
visualize_every = 10      # Save every X episodes for visualisation
training = True
use_model = None
only_visualize = False
# use_model = "12_4_17_collect_agent_memory.h5"
save_file_name = "collect_agent.arl"


# -------------------------------------------


def main():
    episodes = 30

    steps = 1000
    n_ants = 20
    states = []

    min_epsilon = 0.1
    max_epsilon = 0.5

    # Setting up environment
    generator = EnvironmentGenerator(w=200,
                                     h=200,
                                     n_ants=n_ants,
                                     n_pheromones=2,
                                     n_rocks=0,
                                     food_generator=CirclesGenerator(15, 5, 10),
                                     walls_generator=PerlinGenerator(scale=22.0, density=10), # 0.06
                                     max_steps=steps,
                                     seed=None)

    # Setting up RL Reward
    #reward = ExplorationReward()
    # reward_funct = All_Rewards(fct_explore=1, fct_food=5, fct_anthill=100, fct_explore_holding=0.1)
    reward_funct = All_Rewards(fct_explore=1, fct_food=3, fct_anthill=10, fct_explore_holding=0)

    # Setting up RL Api
    api = RLApi(reward=reward_funct,
                reward_threshold=1,
                max_speed=1,
                max_rot_speed=45,
                carry_speed_reduction=0.05,
                backward_speed_reduction=0.5)
    api.save_perceptive_field = True

    # Setting up RL Agent
    agent = CollectAgentMemory(epsilon=0.9,
                         discount=0.99,
                         rotations=3,
                         pheromones=3)

    agent_is_setup = False

    avg_loss = None
    avg_time = None

    print("Starting simulation...")
    for episode in range(episodes):
        env = generator.generate(api)
        print('\n--- Episode {}/{} ---'.format(episode, episodes))

        # Setups the agents only once
        if not agent_is_setup:
            agent.setup(api, use_model)
            agent_is_setup = True

        # Initializes the agents on the new environment
        agent.initialize(api)

        obs, agent_state, state = api.observation()
        episode_reward = np.zeros(n_ants)

        for s in range(steps):
            now = time.time()

            # Compute the next action of the agents
            action = agent.get_action(obs, agent_state, training)

            # Execute the action
            new_state, new_agent_state, reward, done = api.step(*action[:2])

            # Add the reward to total reward of episode
            episode_reward += reward

            # Update replay memory with new action and states
            agent.update_replay_memory(obs, agent_state, action, reward, new_state, new_agent_state, done)

            # Train the neural network
            if training:
                loss = agent.train(done, s)

                if avg_loss is None:
                    avg_loss = loss
                else:
                    avg_loss = 0.99 * avg_loss + 0.01 * loss
            else:
                avg_loss = 0

            # Set obs to the new state
            obs = new_state
            agent_state = new_agent_state

            if (s + 1) % 50 == 0:
                mean_reward = episode_reward.mean()
                max_reward = episode_reward.max()
                min_reward = episode_reward.min()
                var_reward = episode_reward.std()
                total_reward = episode_reward.sum()

                print("\rAverage loss : {:.5f} --".format(avg_loss),
                      "Episode reward stats: mean {:.2f} - min {:.2f} - max {:.2f} - std {:.2f} - total {:.2f} --".format(
                          mean_reward, min_reward, max_reward, var_reward, total_reward),
                      "Avg-time per step: {:.3f}ms, step {}/{}".format(avg_time, s+1, steps),
                      end="")

            # Pass new step
            env.update()

            elapsed = (time.time() - now) * 1000
            if avg_time is None:
                avg_time = elapsed
            else:
                avg_time = 0.99 * avg_time + 0.01 * elapsed

            if (episode + 1) % visualize_every == 0 or episode == 0 or not training:
                states.append(env.save_state())


        agent.epsilon = max(min_epsilon,  min(max_epsilon, 1.0 - math.log10((episode+1)/5)))
        print('\n Epsilon : ', agent.epsilon)

    pickle.dump(states, open("saved/" + save_file_name, "wb"))

    if save_model and training:
        date = datetime.datetime.now()
        model_name = str(date.day) + '_' + str(date.month) + '_' + str(date.hour) + '_' + agent.name + '.h5'
        agent.save_model(model_name)



if __name__ == '__main__':
    if not only_visualize:
        main()

    visualiser = Visualizer()
    visualiser.big_dim = 900
    visualiser.visualize(save_file_name)
