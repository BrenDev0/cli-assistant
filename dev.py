from  src.tools.ghl.tools import search_operations
import asyncio


async def  main():
    tools = await search_operations("get a contact by id")
    print(tools)



if __name__ == "__main__":
    asyncio.run(main())