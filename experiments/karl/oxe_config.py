from copy import deepcopy

from ml_collections import ConfigDict
from ml_collections.config_dict import placeholder
from config import update_config
from orca.data.oxe.oxe_dataset_mixes import *


def get_config(config_string):
    base_wandb_config = dict(
        project="orca", group=placeholder(str), entity=placeholder(str)
    )

    base_config = dict(
        batch_size=256,
        shuffle_buffer_size=10000,
        num_val_batches=8,
        num_steps=int(2e6),
        start_step=placeholder(int),
        log_interval=100,
        eval_interval=10000000,
        save_interval=10000,
        save_dir='gs://karl-central-2',
        resume_path=placeholder(str),
        seed=42,
        text_processor=None,
        text_processor_kwargs=dict(),
        pretrained_weights=[],
        wandb=base_wandb_config,
        eval_datasets=['bridge_dataset'],
    )

    # params that need to be specified multiple places
    normalization_type = "normal"

    base_data_config = dict(
        window_size=4,
        image_augment_kwargs=dict(
            random_resized_crop=dict(scale=[0.8, 1.0], ratio=[0.9, 1.1]),
            random_brightness=[0.2],
            random_contrast=[0.8, 1.2],
            random_saturation=[0.8, 1.2],
            random_hue=[0.1],
            augment_order=[
                "random_resized_crop",
                "random_brightness",
                "random_contrast",
                "random_saturation",
                "random_hue",
            ],
        ),
        goal_relabeling_strategy="uniform",
        action_proprio_normalization_type=normalization_type,
    )

    base_optimizer_config = dict(
        learning_rate=3e-4, warmup_steps=2000, decay_steps=int(2e6)
    )

    base_model_config = dict(
        token_embedding_size=256,
        max_horizon=10,
        readouts=dict(action=7),
        transformer_kwargs=dict(
            num_layers=4,
            mlp_dim=1024,
            num_attention_heads=8,
            dropout_rate=0.1,
        ),
        heads=dict(
            action=dict(
                cls_name="token_per_dim_action_head",
                kwargs=dict(
                    pred_horizon=1,
                    action_dim=7,
                    vocab_size=256,
                    normalization_type=normalization_type,
                    readout_key="action",
                ),
            )
        ),
    )

    base_tokenizer_kwargs = dict(
        encoder="resnetv1-34-bridge",
        encoder_kwargs=dict(
            pooling_method="none", add_spatial_coordinates=True, act="swish"
        ),
        task_stack_keys=[
            "image_.*"
        ],  # by default, early fuse goal images into visual encoder
    )

    dataset_kwargs_list, dataset_sampling_weights = (
        make_oxe_dataset_kwargs_and_weights(
            RT_X_MIX + OXE_FRANKA_MIX,
            data_dir='gs://rail-orca-central2/resize_336_336',
            n_third_person_cameras=1,
            n_wrist_cameras=1,
            load_depth=False,
        )
    )

    possible_structures = {
        "transformer_bc_rtx": ConfigDict(
            dict(
                model=update_config(
                    base_model_config,
                    observation_tokenizers=[
                        (
                            "image_tokenizer",
                            {"num_tokens": 64,
                             "task_film_keys": ["language_instruction"], **base_tokenizer_kwargs},
                        ),
                    ],
                    task_tokenizers=[],
                ),
                optimizer=base_optimizer_config,
                dataset_kwargs={
                    "common_kwargs": update_config(
                        base_data_config,
                        resize_size=(256, 256),
                        ram_budget=1,       # limit RAM per dataset
                        task_augmentation_strategy="switch_keys",
                        task_augmentation_kwargs = dict(
                            switch_key_groups_probs = [
                                (["image_0"], 0.5),
                                (["language_instruction"], 0.5),
                            ],
                        ),
                    ),
                    "data_kwargs_list": dataset_kwargs_list,
                    "sample_weights": dataset_sampling_weights,
                },
                **update_config(
                    base_config,
                    text_processor="muse_embedding",
                ),
            )
        ),
    }

    return possible_structures[config_string]