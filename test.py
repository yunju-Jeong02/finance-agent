from finance_agent import InputNode, QueryParserNode, SqlGeneratorNode

input_node = InputNode()
parser_node = QueryParserNode()
generator_node = SqlGeneratorNode()

# response = generator_node.process({
#     "user_query": "현대사료의 2025-05-12 시가은?",
#     "parsed_query": parser_node.process({
#         "user_query": "현대사료의 2025-05-12 시가은?"
#     })  
# })

state = input_node.process({
    "user_query": "최근 오른 주식 알려줘"
})

print(state)
                             