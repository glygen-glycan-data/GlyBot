"""Script for running Create Read Update Delete Metrics from API/Model Responses"""

# imports
import pandas as pd
import os
from llama_index.core.evaluation import (
    FaithfulnessEvaluator,
    RelevancyEvaluator,
    CorrectnessEvaluator,
    BaseEvaluator
)
from llama_index.core import Document, Settings
from llama_index.core.query_engine import RetrieverQueryEngine
from ragas.testset.generator import TestsetGenerator
from ragas.testset.evolutions import simple, reasoning, multi_context
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from ragas.metrics.critique import harmfulness
from ragas.integrations.llama_index import evaluate

class GlyBot_Evaluator():
    """
    Class for running response evaluation in the main experimentation pipeline.
    """
    def __init__(self, curated_q_path: str, documents: Document, query_engine: RetrieverQueryEngine):
        """
        Initialize the evaluator with the test data and query engine.
        """
        self.documents = documents
        self.curated_q_path = curated_q_path
        self.query_engine = query_engine
        self.llm_metrics = [
            FaithfulnessEvaluator(),
            RelevancyEvaluator(),
            CorrectnessEvaluator()
        ]
        self.ragas_metrics = [
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
            harmfulness
        ]

    def get_prompts(self):
        """
        Processes the test data for evaluation.
        """
        # generate synthetic test set
        generator = TestsetGenerator.from_llama_index(
            generator_llm=Settings.llm,
            critic_llm=Settings.llm,
            embeddings=Settings.embed_model)
        
        synthetic_test_set = generator.generate_with_llamaindex_docs(
            documents = self.documents,
            test_size=20,
            distributions={
                simple: 0.5, 
                reasoning: 0.25, 
                multi_context: 0.25}
            )
        
        synthetic_dict = synthetic_test_set.to_dataset().to_dict()

        self.synthetic_dict = synthetic_dict # new attribute

        # load curated test set
        curated_test_set = pd.read_csv(self.curated_q_path)
        columns = curated_test_set.columns
        curated_dict = {"question":curated_test_set[columns[1]],
                        "ground_truth":curated_test_set[columns[2]]}

        self.curated_dict = curated_dict # new attribute

    def response_evaluation(self):
        """
        Runs the evaluation pipeline.
        """
        llm = Settings.llm
        embed_model = Settings.embed_model

        ragas_synth = evaluate(
            query_engine = self.query_engine,
            metrics = self.ragas_metrics,
            dataset = self.synthetic_dict,
            llm=llm,
            embeddings=embed_model
        )
        """llm_synth = evaluate(
            query_engine = self.query_engine,
            metrics = self.llm_metrics,
            dataset = self.synthetic_dict,
            llm=llm,
            embeddings=embed_model
        )"""
        ragas_curated = evaluate(
            query_engine = self.query_engine,
            metrics = self.ragas_metrics,
            dataset = self.curated_dict,
            llm=llm,
            embeddings=embed_model
        )
        """llm_curated = evaluate(
            query_engine = self.query_engine,
            metrics = self.llm_metrics,
            dataset = self.curated_dict,
            llm=llm,
            embeddings=embed_model
        )"""
        results = [("ragas_synth",ragas_synth), 
                   #("llm_synth",llm_synth), 
                   ("ragas_curated",ragas_curated), 
                   #("llm_curated",llm_curated)
                   ]
        
        def set_result_path():
            """
            recursively tries to set a new result path for each evaluation run
            so results are not saved over each other.
            """
            result_path = "./response_evaluation"
            loc = 0
            while os.path.exists(result_path):
                loc+=1
                result_path = f"./response_evaluation_{loc}"

            return result_path

        path = set_result_path()  
          
        for data in results:
            df = data[1].to_pandas()
            df.to_csv(f"{path}/{data[0]}.csv")