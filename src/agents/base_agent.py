from abc import abstractmethod
from utils.register import register_class


@register_class(alias="Agent.Base")
class Agent(object):
    def __init__(self, engine):
        self.engine = engine
        self.memories = [("system", self.system_message)]
    
    @staticmethod
    def add_parser_args(parser):
        pass

    def memorize(self, message):
        self.memories.append(message)

    def forget(self):
        self.memories = [("system", self.system_message)]
    
    def show_memories(self):
        print ("--------------- Memory ---------------")
        for memory in self.memories:
            print ("--------------------------------------")
            print (memory[0])
            print (memory[1])
        print ()

    def summarizewithspr(self, rawinput=""):
        from agents.prompt_templates.principles.thought import system_prompt_spr

        messages = [{"role": "system", "content": system_prompt_spr},
            {"role": "user", "content": rawinput}]
        spr_representation = self.engine.get_response(messages)

        return spr_representation


    @abstractmethod
    def speak(self, message, save_to_memory=True):
        pass