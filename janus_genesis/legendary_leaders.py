# janus_genesis/legendary_leaders.py
import random

class LegendaryLeader:
    def __init__(self, agent):
        self.agent = agent
        self.charisma = random.uniform(1, 3)
        self.legend_score = 0

class LegendaryLeaderSystem:
    def __init__(self, world, event_bus):
        self.world = world
        self.event_bus = event_bus
        self.leaders = []
        event_bus.subscribe("raid_win", self.on_raid_win)

    def on_raid_win(self, agents, boss_name):
        for agent in agents:
            if agent.level > 8 and random.random() < 0.2:
                leader = LegendaryLeader(agent)
                self.leaders.append(leader)
                print(f"🌟 Legendary Leader Emerged: {agent.id[:6]}")
                self.event_bus.emit("legendary_leader_appeared", leader=leader)

    def influence_world(self):
        for leader in self.leaders:
            # Влияние на ближайших (в одной локации или фракции)
            followers = [a for a in self.world.population if a.faction == leader.agent.faction]
            if followers:
                sample_size = min(5, len(followers))
                for f in random.sample(followers, sample_size):
                    f.score += leader.charisma * 0.1