import re
import logging

logger = logging.getLogger(__name__)

def parse_llm_response(response_text: str) -> dict:
    """
    Parses the LLM response text to extract Thought, Action, Action Input, and Final Answer.
    Uses regex based on the expected format. More robust parsing might be needed for complex cases.
    """
    thought_match = re.search(r"Thought:\s*(.*?)(?:\nAction:|\Z)", response_text, re.DOTALL | re.IGNORECASE)
    action_match = re.search(r"Action:\s*(.*?)(?:\nAction Input:|\Z)", response_text, re.DOTALL | re.IGNORECASE)
    action_input_match = re.search(r"Action Input:\s*(.*?)(?:\nObservation:|\Z)", response_text, re.DOTALL | re.IGNORECASE)
    final_answer_match = re.search(r"Final Answer:\s*(.*)", response_text, re.DOTALL | re.IGNORECASE)

    thought = thought_match.group(1).strip() if thought_match else ""
    action = action_match.group(1).strip() if action_match else ""
    action_input = action_input_match.group(1).strip() if action_input_match else ""
    final_answer = final_answer_match.group(1).strip() if final_answer_match else None

    # Basic validation
    if not thought and not final_answer:
        logger.warning(f"Could not parse 'Thought' from response: {response_text}")
        # Attempt fallback or return error structure? For now, allow continuation.

    if not action and not final_answer:
         logger.warning(f"Could not parse 'Action' from response: {response_text}")
         # Might indicate LLM is confused or finished without using Final Answer tag

    # Action input might be legitimately empty for some actions
    # if action and not action_input:
    #     logger.warning(f"Action specified ('{action}') but could not parse 'Action Input'. Assuming empty input.")


    parsed = {
        "thought": thought,
        "action": action,
        "action_input": action_input,
        "final_answer": final_answer
    }

    # Log if the LLM provided a final answer
    if final_answer:
        logger.info(f"LLM provided Final Answer: {final_answer}")
        # Reset action/input if final answer is given, as no action should be taken
        parsed["action"] = None
        parsed["action_input"] = None

    # Log if no action is parsed but also no final answer (could indicate problem)
    elif not action:
         logger.warning(f"LLM did not provide an Action or a Final Answer. Response: {response_text}")


    return parsed


if __name__ == '__main__':
    # Example Usage
    test_response_1 = """
    Thought: I need to find out the capital of France. I should use the web search tool.
    Action: web_search
    Action Input: capital of France
    """
    parsed1 = parse_llm_response(test_response_1)
    print("Parsed 1:", parsed1)
    assert parsed1['thought'] == "I need to find out the capital of France. I should use the web search tool."
    assert parsed1['action'] == "web_search"
    assert parsed1['action_input'] == "capital of France"
    assert parsed1['final_answer'] is None

    test_response_2 = """
    Thought: The user asked for the content of 'myfile.txt'. I should use the file reader tool.
    Action: read_file
    Action Input: myfile.txt
    Observation: Successfully read file. Content: Hello World!
    Thought: I have the content. I should provide it as the final answer.
    Final Answer: The content of myfile.txt is: Hello World!
    """
    # Note: Parsing only looks for the *last* thought/action/input block typically,
    # or specifically for the Final Answer tag. Let's test parsing the final answer part.
    parsed2 = parse_llm_response(test_response_2) # Simulates parsing the final part
    print("\nParsed 2:", parsed2)
     # This test depends on how exactly the agent constructs the prompt history
     # Let's test just the final answer part directly
    final_answer_response = "Thought: Goal achieved.\nFinal Answer: The capital of France is Paris."
    parsed_final = parse_llm_response(final_answer_response)
    print("\nParsed Final:", parsed_final)
    assert parsed_final['thought'] == "Goal achieved."
    assert parsed_final['action'] is None # Action should be ignored if Final Answer is present
    assert parsed_final['action_input'] is None
    assert parsed_final['final_answer'] == "The capital of France is Paris."


    test_response_3 = """
    Thought: I should list the files in the current directory.
    Action: list_directory
    Action Input: .
    """
    parsed3 = parse_llm_response(test_response_3)
    print("\nParsed 3:", parsed3)
    assert parsed3['action'] == "list_directory"
    assert parsed3['action_input'] == "." # Handles empty or simple inputs

    test_response_4 = "Final Answer: The task is complete." # Only final answer
    parsed4 = parse_llm_response(test_response_4)
    print("\nParsed 4:", parsed4)
    assert parsed4['thought'] == "" # No thought provided
    assert parsed4['action'] is None
    assert parsed4['action_input'] is None
    assert parsed4['final_answer'] == "The task is complete."

    test_response_5 = "Thought: Thinking...\nAction: my_tool\nAction Input: some data here" # No Observation/Final Answer
    parsed5 = parse_llm_response(test_response_5)
    print("\nParsed 5:", parsed5)
    assert parsed5['thought'] == "Thinking..."
    assert parsed5['action'] == "my_tool"
    assert parsed5['action_input'] == "some data here"
    assert parsed5['final_answer'] is None

    test_response_6 = "Thought: Something went wrong.\nAction: error_reporter\nAction Input:" # Empty Action Input
    parsed6 = parse_llm_response(test_response_6)
    print("\nParsed 6:", parsed6)
    assert parsed6['thought'] == "Something went wrong."
    assert parsed6['action'] == "error_reporter"
    assert parsed6['action_input'] == "" # Correctly parses empty input
    assert parsed6['final_answer'] is None