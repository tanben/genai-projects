import json
from dotenv import dotenv_values
from langchain_community.llms import Ollama
from langchain.chains import GraphCypherQAChain
from langchain.prompts import (PromptTemplate)
from langchain_community.graphs import Neo4jGraph

config = dotenv_values()

NEO4J_URI = config.get("NEO4J_URI")
NEO4J_USER = config.get('NEO4J_USER')
NEO4J_PASS = config.get("NEO4J_PASS")
NEO4J_TIMEOUT = config.get("NEO4J_TIMEOUT")
LLM_MODEL = config.get("LLM_MODEL")
LLM_BASE_URL = config.get('LLM_BASE_URL')

instance_model = """
MERGE (:User {name: "Chris", orgRole: "flagmgr"})-[:MEMBER_OF]->(:Team {name: "t1-flagmanager"})-[:HAS_ROLE]->(n12:Role {name: "flagManager", type: "custom"})-[:ALLOW {permissions: ["createFlag", "updateFlagVariations"], resource: "flag", environments: ["DEV", "QA","PROD"]}]->(`toggle-a`:Flag {name: "toggle-a"})-[:NO_APPROVAL]->(:Environment {name: "dev"})<-[:HAS_ENVIRONMENT]-(n0:Project {name: "sample-project"})-[:HAS_ENVIRONMENT]->(Production:Environment {name: "prod"})<-[:WITH_APPROVAL]-(`toggle-a`)-[:NO_APPROVAL]->(QA:Environment {name: "qa"})
MERGE (:Team {name: "t1-read"})-[:HAS_ROLE]->(n4:Role {name: "reader", type: "custom"})-[:ALLOW {permissions: ["viewProject"], resource: "project"}]->(n0)-[:HAS_ENVIRONMENT]->(QA)
MERGE (ben:User {name: "Ben", orgRole: "developer"})-[:MEMBER_OF]->(n6:Team {name: "t1-contributor"})-[:HAS_ROLE]->(:Role {name: "contributor", type: "custom"})-[:ALLOW {permissions: ["updateRules","updateTargets"], resource: "flag", environments: ["DEV", "QA","PROD"]}]->(`toggle-a`)
MERGE (:User {name: "Jim", orgRole: "analyst"})-[:MEMBER_OF]->(n6)-[:HAS_ROLE]->(n4)
MERGE (t1Approver:Team {name: "t1-approver"})-[:HAS_ROLE]->(n15:Role {name: "approver", type: "custom"})-[:ALLOW {permissions: ["reviewApprovalRequest","applyApprovalRequest"], resource: "environment"}]->(Production)
MERGE (:Team {name: "t2-approver"})-[:HAS_ROLE]->(n15)
MERGE (:User {name: "Rick", orgRole: "flagmgr"})-[:MEMBER_OF]->(:Team {name: "t2-flagmanager"})-[:HAS_ROLE]->(n12)
Merge (ben)-[:MEMBER_OF]->(t1Approver)
"""

cypher_template = """ 
Task: 
You are an expert Neo4j Developer translating user questions into Cypher to answer questions about LaunchDarkly custom roles. 
Convert the user's question based on the schema. 


Instructions: 
Use only Cypher statement in your response.
Use only the provided relationship types and properties in the schema. 
Do not use any other relationship types or properties that are not provided.
If no data is returned, do not attempt to answer the question. 
Only respond to questions that require you to construct a Cypher statement. 
Do not include any explanations or apologies in your responses. 


Cypher examples:
List permissions 
match (n)-[a:ALLOW]->(z) return a.permissions, a.environments
List teams
match (t:Team) return t.name 
Count the number of teams.
match (t:Team) return count(t)
List team permissions.
match (t:Team)-[:HAS_ROLE]->(r:Role)-[a:ALLOW]->(f)  a.permissions
List team members.
match (t:Team)<-[:MEMBER_OF]-(u:User) return u.name
List roles.
match (r:Role) return r.name as Role
Count number of roles.
match (r:Role) return count (r)
List all user roles.
match (u:User)-[:MEMBER_OF]->(t:Team)-[:HAS_ROLE]->(r:Role) return u.name, r.name
List James roles
match (u:User)-[:MEMBER_OF]->(t:Team)-[:HAS_ROLE]->(r:Role) where u.name="James" return r.name
List  James permissions.
match (u:User)-[:MEMBER_OF]->(t:Team)-[:HAS_ROLE]->(r:Role)-[a:ALLOW]->(f)  where u.name="James" return  a.permissions
Find users with developer role
match (u:User)-[:MEMBER_OF]->(t:Team)-[:HAS_ROLE]->(r:Role) where  r.name='developer' return u.name
List team and it's members.
match (u:User)-[:MEMBER_OF]->(t.Team) where t.name, u.name


Schema: {schema} 
Question: {question} 
"""

llm = Ollama(base_url=LLM_BASE_URL, model=LLM_MODEL,
             temperature=0, verbose=False)
graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USER,
                   password=NEO4J_PASS, timeout=NEO4J_TIMEOUT)

graph.query(instance_model)


cypher_prompt = PromptTemplate(
    template=cypher_template,
    input_variables=["schema", "question"],
)


chain = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    verbose=True,
    cypher_prompt=cypher_prompt
)

questions = [
    {"question": "List all team members in a table."},
    {"question": "List team member of t1-contributor."},
    {"question": "List users that includes a flagManager role."},
    {"question": "List users, team assignments and permissions in a table sorted by member."},
]

for question in questions:
    print('\n------------------------------------')
    print(f"Query: {question.get('question')}")
    result = chain.invoke(json.dumps(question))
    print(result.get('result'))
    print('------------------------------------\n')
