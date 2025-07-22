from finance_agent import QueryParserNode

parser_node = QueryParserNode()

response = parser_node.process({
    "user_query": "피코그램의 2024-09-10 종가는?"
})

print(response)
                             