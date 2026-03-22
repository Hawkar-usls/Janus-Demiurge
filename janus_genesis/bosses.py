class RaidBoss:

    def __init__(self, name, hp):

        self.name = name
        self.hp = hp

    def damage(self, value):

        self.hp -= value

        if self.hp <= 0:

            print(f"[🏆] Рейд-босс {self.name} повержен!")
