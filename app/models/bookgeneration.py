import os
import asyncio
import re
from typing import Annotated, List, Optional, Dict, Any
from typing_extensions import TypedDict

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from dotenv import load_dotenv
from app.services.google_docs import GoogleDocsHelper
from app.db import MongoDB
from app.core.config import DataBaseSettings

load_dotenv(override=True)

class State(TypedDict):
    messages: Annotated[list, add_messages]
    title: str
    sanitized_title: str
    notes_before_outline: str
    outline: str
    outline_doc_url: str
    notes_on_outline_after: Optional[str]
    chapters: List[str]
    chapter_summaries: List[Dict[str, Any]]
    current_chapter_number: int
    user_decision: str
    chapter_feedback: Optional[str]
    final_review_notes: Optional[str]

class BookGeneration:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
        self.docs = GoogleDocsHelper()
        self.db = MongoDB(DataBaseSettings())

        graph_builder = StateGraph(State)
        graph_builder.add_node("generate_outline", self.generate_outline_node)
        graph_builder.add_node("write_initial_outline_to_doc", self.write_initial_outline_to_doc)
        graph_builder.add_node("get_outline_feedback", self.get_outline_feedback)
        graph_builder.add_node("regenerate_outline", self.regenerate_outline)
        graph_builder.add_node("generate_chapter", self.generate_chapter)
        graph_builder.add_node("get_chapter_feedback", self.get_chapter_feedback)
        graph_builder.add_node("regenerate_chapter", self.regenerate_chapter)
        graph_builder.add_node("summarize_and_save_chapter", self.summarize_and_save_chapter)
        graph_builder.add_node("get_next_chapter_decision", self.get_next_chapter_decision)
        graph_builder.add_node("get_final_review_notes", self.get_final_review_notes)
        graph_builder.add_node("perform_final_revision", self.perform_final_revision)
        graph_builder.add_node("finish", self.finish_node)


        graph_builder.add_edge(START, "generate_outline")
        graph_builder.add_edge("generate_outline", "write_initial_outline_to_doc")
        graph_builder.add_edge("write_initial_outline_to_doc", "get_outline_feedback")
        graph_builder.add_conditional_edges("get_outline_feedback", self.decide_on_outline_feedback, {"revise": "regenerate_outline", "approve": "generate_chapter"})
        graph_builder.add_edge("regenerate_outline", "get_outline_feedback")
        graph_builder.add_edge("generate_chapter", "get_chapter_feedback")
        graph_builder.add_conditional_edges("get_chapter_feedback", self.decide_to_regenerate_chapter, {"regenerate": "regenerate_chapter", "approve": "summarize_and_save_chapter"})
        graph_builder.add_edge("regenerate_chapter", "summarize_and_save_chapter")
        graph_builder.add_edge("summarize_and_save_chapter", "get_next_chapter_decision")
        graph_builder.add_conditional_edges("get_next_chapter_decision", self.should_generate_next_chapter, {"continue": "generate_chapter", "stop": "get_final_review_notes"})
        graph_builder.add_conditional_edges("get_final_review_notes", self.decide_on_final_revision, {"revise": "perform_final_revision", "finish": "finish"})
        graph_builder.add_edge("perform_final_revision", "finish")
        graph_builder.add_edge("finish", END)

        self.checkpointer = InMemorySaver()
        self.graph = graph_builder.compile(checkpointer=self.checkpointer)

    async def initialize(self):
        await self.db.initialize()


    def _sanitize_filename(self, filename: str) -> str: return re.sub(r'[\\/*?:"<>|]', "", filename)
    def _read_file_content(self, filename: str) -> str:
        try:
            with open(filename, 'r', encoding='utf-8') as f: return f.read()
        except FileNotFoundError: return ""
    def _sync_write_to_text_file(self, filename: str, content: str):
        with open(filename, 'w', encoding='utf-8') as f: f.write(content)



    def get_outline_feedback(self, state: State) -> Dict[str, Any]:
        print(f"\n--- WAITING FOR OUTLINE FEEDBACK ---\nThe book outline is in the Google Doc:\n{state['outline_doc_url']}")
        return {"notes_on_outline_after": input("Please review the outline. \n- To approve, type 'ok' or press Enter.\n- To request revisions, describe them here: ")}
    def get_chapter_feedback(self, state: State) -> Dict[str, Any]:
        print(f"\n--- WAITING FOR FEEDBACK ON CHAPTER {state['current_chapter_number']} ---\nChapter {state['current_chapter_number']} has been added to the Google Doc and saved locally.")
        return {"chapter_feedback": input("Please review the latest chapter. \n- To approve, type 'ok', 'good', or 'next'.\n- To request revisions, describe the changes you want: ")}
    def get_next_chapter_decision(self, state: State) -> Dict[str, Any]:
        print("\n--- PROCEED TO NEXT CHAPTER? ---\nNote: Once you proceed, you cannot make changes to previous chapters.")
        while True:
            decision = input("Would you like to generate the next chapter? (yes/no): ").lower().strip()
            if decision in ["yes", "y", "no", "n"]: break
            print("Invalid input. Please enter 'yes' or 'no'.")
        return {"user_decision": decision, "current_chapter_number": state['current_chapter_number'] + 1}
    def get_final_review_notes(self, state: State) -> Dict[str, Any]:
        print(f"\n--- FINAL REVIEW ---\nAll chapters have been written and saved to '{state['sanitized_title']}.txt'.")
        return {"final_review_notes": input("Please perform a final review. \n- To finish, type 'none' or press Enter.\n- To request a final revision, describe the changes: ")}


    async def generate_outline_node(self, state: State) -> Dict[str, Any]:
        print("--- Generating Outline ---")
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert book author..."), ("human", "Title: {title}\nInitial Notes: {notes_before_outline}")
        ])
        chain = prompt | self.llm
        return {"outline": (await chain.ainvoke(state)).content, "outline_doc_url": self.docs.doc_url}

    async def write_initial_outline_to_doc(self, state: State) -> Dict[str, Any]:
        print("--- Writing initial outline to Google Doc and DB ---")
        outline = state['outline']
        self.docs.write_to_doc(f"OUTLINE\n\n---\n\n{outline}", clear_before_writing=True)
        await self.db.update_book_outline(book_title=state['title'], outline_md=outline)
        return {}

    async def regenerate_outline(self, state: State) -> Dict[str, Any]:
        print("--- Regenerating Outline based on feedback ---")
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert book author..."), ("human", "Original Outline:\n{outline}\n\nUser Feedback:\n{feedback}\n\nPlease generate a new, complete outline...")
        ])
        chain = prompt | self.llm
        new_outline = (await chain.ainvoke({"outline": state["outline"], "feedback": state["notes_on_outline_after"]})).content
        
        self.docs.write_to_doc(f"OUTLINE\n\n---\n\n{new_outline}", clear_before_writing=True)
        await self.db.update_book_outline(state['title'], new_outline)
        
        return {"outline": new_outline}

    async def generate_chapter(self, state: State) -> Dict[str, Any]:
        chapter_num = state['current_chapter_number']
        print(f"--- Generating Chapter {chapter_num} ---")
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a master storyteller..."),
            ("human", "Book Title: {title}\nOverall Outline:\n{outline}\n\nAll Previous Chapter Summaries:\n{chapter_summaries}\n\nNow, write Chapter {chapter_num} in its entirety.")
        ])
        chain = prompt | self.llm
        response = await chain.ainvoke({"title": state["title"], "outline": state["outline"], "chapter_summaries": "\n".join([f"Ch {s['chapter_number']}: {s['summary']}" for s in state['chapter_summaries']]), "chapter_num": chapter_num})
        chapter_content = response.content

        book_filename = f"{state['sanitized_title']}.txt"
        chapter_header = f"\n\n---\n\nChapter {chapter_num}\n\n---\n\n"
        
        full_text = self._read_file_content(book_filename) + chapter_header + chapter_content
        self._sync_write_to_text_file(book_filename, full_text)
        self.docs.append_to_doc(chapter_header + chapter_content)

        print(f"Chapter {chapter_num} generated and saved.")
        return {"chapters": [chapter_content]}

    async def regenerate_chapter(self, state: State) -> Dict[str, Any]:
        chapter_num = state['current_chapter_number']
        print(f"--- Regenerating Chapter {chapter_num} with full logic ---")
        prompt = ChatPromptTemplate.from_messages([
             ("system", "You are a master storyteller..."), ("human", "Original Chapter {chapter_num} Content:\n{original_chapter}\n\nFeedback for revision: {feedback}\n\nPlease rewrite Chapter {chapter_num}...")])
        chain = prompt | self.llm
        revised_response = await chain.ainvoke({"chapter_num": chapter_num, "original_chapter": state['chapters'][-1], "feedback": state['chapter_feedback']})
        revised_content = revised_response.content
        
        book_filename = f"{state['sanitized_title']}.txt"
        full_manuscript = self._read_file_content(book_filename)
        
        pattern = re.compile(fr"(---\s*\n\nChapter {chapter_num}\s*\n\n---.*?)(---\s*\n\nChapter {chapter_num + 1}|\Z)", re.DOTALL)
        replacement_text = f"---\n\nChapter {chapter_num}\n\n---\n\n{revised_content}"
        
        if pattern.search(full_manuscript):
            updated_manuscript = pattern.sub(rf"{replacement_text}\2", full_manuscript, count=1)
            self._sync_write_to_text_file(book_filename, updated_manuscript)
            print("Chapter successfully replaced in the local manuscript file.")

            full_doc_content = f"OUTLINE\n\n---\n\n{state['outline']}\n{updated_manuscript}"
            self.docs.write_to_doc(full_doc_content, clear_before_writing=True)
            print("Google Doc has been updated with the revised chapter.")
        else:
             print("Warning: Could not find chapter in file to replace. Appending instead.")
             self._sync_write_to_text_file(book_filename, full_manuscript + "\n" + replacement_text)

        return {"chapters": [revised_content]}


    async def summarize_and_save_chapter(self, state: State) -> Dict[str, Any]:
        chapter_num = state['current_chapter_number']
        print(f"--- Summarizing and Saving Chapter {chapter_num} ---")
        prompt = ChatPromptTemplate.from_template("Summarize the following book chapter in 2-4 sentences: \n\n{chapter}")
        chain = prompt | self.llm
        summary = (await chain.ainvoke({"chapter": state['chapters'][-1]})).content

        new_summary = {"chapter_number": chapter_num, "summary": summary}
        updated_summaries = state.get("chapter_summaries", []) + [new_summary]
        await self.db.update_book_chapters(state['title'], updated_summaries)
        return {"chapter_summaries": updated_summaries}

    async def perform_final_revision(self, state: State) -> Dict[str, Any]:
        print(f"--- Performing Final Manuscript Revision ---")
        book_filename = f"{state['sanitized_title']}.txt"
        full_manuscript = self._read_file_content(book_filename)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a professional editor..."),("human", "Here is the complete manuscript:\n\n---\n\n{manuscript}\n\n---\n\nHere are my final revision notes:\n\n{notes}\n\nPlease provide the complete, revised manuscript.")])
        chain = prompt | self.llm
        response = await chain.ainvoke({"manuscript": full_manuscript, "notes": state["final_review_notes"]})
        revised_manuscript = response.content

        self._sync_write_to_text_file(book_filename, revised_manuscript)
        print("Final revised manuscript has been saved to the local file.")
        
        final_section = f"\n\n\n{'='*20}\n\nFINAL REVISED MANUSCRIPT\n\n{'='*20}\n\n{revised_manuscript}"
        self.docs.append_to_doc(final_section)
        print("Final manuscript appended to the Google Doc.")
        return {}



    def decide_on_outline_feedback(self, state: State) -> str: return "approve" if not state.get("notes_on_outline_after", "").strip().lower() or state.get("notes_on_outline_after", "").strip().lower() in ["ok", "looks good", "good", "approve"] else "revise"
    def decide_to_regenerate_chapter(self, state: State) -> str: return "approve" if state.get("chapter_feedback", "").strip().lower() in ["ok", "looks good", "good", "continue", "next", "approve"] else "regenerate"
    def should_generate_next_chapter(self, state: State) -> str: return "continue" if "y" in state.get("user_decision", "") else "stop"
    def decide_on_final_revision(self, state: State) -> str: notes = state.get("final_review_notes", "").strip().lower(); return "finish" if not notes or notes in ["none", "no", "skip"] else "revise"
    def finish_node(self, state: State) -> Dict: print(f"\n--- BOOK GENERATION COMPLETE ---\nFinal manuscript saved as: '{state['sanitized_title']}.txt'\nProject workbook available at: {state['outline_doc_url']}"); return {}

async def main():
    try:
        print("--- Starting a New Book Generation Workflow ---")
        title = input("Enter the title for your book: ")
        if not title: print("Title cannot be empty. Exiting."); return
        
        print("Enter initial notes for your book (Ctrl+D or Ctrl+Z on a new line to finish):")
        notes_lines = []
        while True:
            try: notes_lines.append(input())
            except EOFError: break
        notes_before_outline = "\n".join(notes_lines)
        if not notes_before_outline: print("Initial notes cannot be empty. Exiting."); return

        book_gen = BookGeneration()
        await book_gen.initialize()

        sanitized_title = book_gen._sanitize_filename(title)
        config = {"configurable": {"thread_id": f"book-gen-{sanitized_title}-{os.urandom(2).hex()}"}}

        initial_state = {
            "title": title, "sanitized_title": sanitized_title,
            "notes_before_outline": notes_before_outline,
            "chapters": [], "chapter_summaries": [],
            "current_chapter_number": 1,
            "messages": [HumanMessage(content="Start the book generation process.")]
        }

        async for event in book_gen.graph.astream(initial_state, config=config):
            for key, value in event.items():
                print(f"\n... Executed Node: {key} ...")

    except Exception as e:
        import traceback
        print(f"\nAn unexpected error occurred: {e}")
        traceback.print_exc()
    except KeyboardInterrupt:
        print("\nBot stopped by user.")

if __name__ == "__main__":
    asyncio.run(main())