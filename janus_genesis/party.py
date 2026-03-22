# janus_genesis/party.py
import uuid

class Party:
    """Группа агентов."""
    def __init__(self, leader):
        self.id = str(uuid.uuid4())
        self.leader = leader
        self.members = [leader]
        self.created_time = 0  # будет установлено миром

    def add_member(self, agent):
        if agent not in self.members:
            self.members.append(agent)

    def remove_member(self, agent):
        if agent in self.members and agent != self.leader:
            self.members.remove(agent)

    def get_power(self):
        """Суммарная сила группы (для рейдов)."""
        return sum(m.level + m.score for m in self.members)

    def is_active(self):
        return len(self.members) >= 2

class PartySystem:
    def __init__(self):
        self.parties = []

    def create_party(self, leader):
        party = Party(leader)
        self.parties.append(party)
        return party

    def disband_party(self, party):
        if party in self.parties:
            self.parties.remove(party)

    def find_party_by_member(self, agent):
        for p in self.parties:
            if agent in p.members:
                return p
        return None

    def update(self, world):
        """Обновление групп: удаляем пустые, проверяем лидеров."""
        for party in self.parties[:]:
            if len(party.members) < 2:
                self.parties.remove(party)
            else:
                # Если лидер покинул группу или умер, назначаем нового
                if party.leader not in party.members:
                    if party.members:
                        party.leader = party.members[0]
                    else:
                        self.parties.remove(party)