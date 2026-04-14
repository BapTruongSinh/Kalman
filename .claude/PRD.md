# Product Requirements Document

> [!WARNING]
> **HUMAN APPROVAL REQUIRED TO EDIT**
> This document is the source of truth for what we are building.
> Claude agents must READ this document to understand requirements.
> **Do not edit, rewrite, or "update to reflect current state" unless the human has explicitly instructed you to do so in the current conversation.**
> When in doubt, leave it unchanged and ask the human.

---

**Version**: 1.0
**Status**: Draft
**Last updated by human**: [2026-24-02]
**Product owner**: [K]

---

## 1. Executive Summary

This product is a smart greenhouse monitoring and control system designed to help users manage environmental conditions more effectively. It solves the problem of inefficient manual monitoring by collecting real-time data from sensors such as temperature, air humidity, soil moisture, and light intensity, then using that data to support automatic or semi-automatic control decisions. The primary users are farmers, greenhouse operators, and researchers who need a more accurate and efficient way to maintain optimal growing conditions. After using this system, users can improve crop health, reduce water and energy waste, and make faster, data-driven decisions for greenhouse management.

---

## 2. Problem Statement

### 2.1 Current Situation

Today, without this product, greenhouse management is still mostly based on manual observation and simple rule-based actions. Users usually check temperature, humidity, soil moisture, and light conditions by looking at separate measuring devices or by directly observing the plants, then decide when to water, spray mist, or turn on fans based on experience. In many cases, records are written down manually or not stored at all, which makes it difficult to track trends, predict environmental changes, or optimize resource usage. As a result, the process is time-consuming, less accurate, and highly dependent on human attention, which can lead to water waste, unstable growing conditions, and reduced crop quality.

### 2.2 The Problem

The core problem is not simply a lack of monitoring, but the inability to make **accurate, timely, and optimal control decisions** in a greenhouse environment where multiple variables interact continuously. In the current setup, soil moisture, air temperature, relative humidity, and light intensity change together over time, while the available sensor readings are often noisy, delayed, incomplete, or inconsistent. Because of this, direct threshold-based control such as “if soil moisture is low, turn on the pump” or “if humidity is high, turn on the fan” is too simplistic and often produces unstable or inefficient behavior. It cannot properly account for coupling effects between variables, for example watering may increase soil moisture but also affect humidity, while ventilation may reduce humidity but also influence temperature.

A second major problem is that greenhouse control is inherently a  **multi-objective and constrained decision-making task** . The system must keep environmental variables within acceptable ranges for plant growth, while also minimizing water use, energy consumption, and excessive actuator switching. In practice, decisions such as how many seconds to irrigate, whether to activate misting, or when to run ventilation cannot be made effectively by looking only at the current measurement. They require a prediction of how the greenhouse state will evolve over the next several time steps. Without predictive control, the system tends to react too late, overcorrect, or oscillate around the desired range.

Another key issue is that the raw sensor values cannot always be trusted as the true system state. Soil moisture sensors may fluctuate, humidity sensors may contain noise, and real measurements may not fully reflect the underlying condition of the greenhouse. If control decisions are based directly on these imperfect measurements, the controller may respond to noise instead of the real process, causing unnecessary watering, misting, or fan operation. Therefore, the project needs an **Adaptive Kalman Filter** to estimate the hidden or cleaned state more reliably, while adjusting to time-varying uncertainty and sensor disturbances.

At a higher level, the unmet need is for an intelligent control framework that can both **estimate the real greenhouse state** and **optimize future control actions** under uncertainty. This is why the project requires the combination of **Adaptive Kalman filtering** for robust state estimation and **Hybrid Model Predictive Control (HMPC)** for decision-making. HMPC is needed because the greenhouse contains hybrid behavior: continuous state variables such as temperature, humidity, and soil moisture, together with discrete or bounded actuator actions such as pump on/off duration, mist activation, and fan operation. Traditional manual control or simple rule-based automation cannot handle this complexity well enough to guarantee stable plant conditions, efficient resource usage, and anticipatory control performance.

### 2.3 Why Now

This is the right time to build the product because agriculture is under growing pressure to become more precise, resilient, and resource-efficient. FAO reports that agriculture remains the dominant user of freshwater globally, representing about 72% of total freshwater withdrawals in 2020, and UNESCO similarly notes that agriculture uses roughly 70% of freshwater withdrawals worldwide. At the same time, WMO reports that 2024 was the warmest year in the 175-year observational record, with key climate indicators again reaching record levels. Together, these conditions make greenhouse management more important and also more difficult, because growers must maintain stable crop conditions while dealing with stronger environmental variability and tighter water-use constraints.

The timing is also favorable because controlled-environment agriculture and greenhouse automation are becoming more relevant in practice. USDA reported in 2024 that controlled-environment agriculture production and operations have been rising, while Rabobank’s 2025 greenhouse update found positive investment sentiment in the global greenhouse sector and identified labor scarcity, automation demand, and environmental-footprint pressure as key trends. In other words, the need is no longer just academic: growers increasingly need systems that can automate climate and irrigation decisions with better consistency than manual operation.

A second reason is that the technology stack needed for this PBL is now mature, accessible, and affordable enough to prototype realistically. Espressif’s official documentation states that ESP32 can operate as a complete standalone system and provides built-in Wi-Fi and Bluetooth connectivity. On the software side, Node-RED is positioned as a low-code, event-driven platform for collecting and visualizing data, Eclipse Mosquitto is a lightweight open-source MQTT broker, InfluxDB is designed specifically for time-series data with real-time ingest and query, and Grafana is an open-source platform for real-time visualization and dashboards. That means the full path from sensor acquisition to streaming, storage, monitoring, and control is no longer difficult to assemble with open tools.

This matters especially for your project because **now** is also the right time to move beyond simple threshold control and build  **HMPC with Adaptive Kalman filtering** . UNDP notes that modern controlled-environment agriculture increasingly relies on AI, machine learning, IoT, cameras, and sensors to manage growing environments more consistently, while also acknowledging that current systems can still be costly and technically demanding. From that trend, it is reasonable to infer that a low-cost research prototype which combines robust state estimation and predictive control is timely: Adaptive Kalman can reduce the effect of noisy sensor readings, and HMPC can optimize future actions such as irrigation duration, misting, and ventilation under coupled dynamics and actuator constraints rather than reacting only after threshold violations occur.

There is also a clear opportunity in the Vietnam context. FAO’s work in Vietnam highlights smart farming approaches that aim to increase production while using natural resources efficiently, and a 2026 government summary of FAO cooperation priorities in Vietnam emphasizes climate-smart agriculture, efficient water use, soil protection, and lower emissions. For a PBL, this creates strong justification: the project is not only technically feasible, but also aligned with a real regional need for affordable, data-driven greenhouse management systems that can later be expanded into practical deployment, research platforms, or commercial solutions.

---

## 3. Goals & Success Metrics

### 3.1 Business Goals

* **Goal 1: Improve environmental control accuracy and stability in the greenhouse**

  Develop a system that can maintain key environmental variables such as soil moisture, temperature, and relative humidity within desired ranges more consistently than manual control or simple threshold-based automation.
* **Goal 2: Reduce resource waste and improve operational efficiency**

  Minimize unnecessary water usage, energy consumption, and excessive actuator switching by using predictive control to choose more efficient irrigation, misting, and ventilation actions.
* **Goal 3: Build a practical intelligent control platform for future deployment and research**

  Create a working prototype that integrates real-time sensing, state estimation with Adaptive Kalman Filter, and decision-making with HMPC, so it can serve as both a deployable greenhouse solution and a foundation for future academic or commercial development.

### 3.2 Success Metrics

|  |  |  |  |
| - | - | - | - |

| Metric                                                            | Baseline                                           | Target                                                                  | How Measured                                                                                                                                                                                                                 |
| ----------------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Soil moisture within target range (%)**                   | 55–65% of operating time                          | **≥ 85%**of operating time                                             | Calculate the percentage of sampled time steps where soil moisture stays within the defined safe band[Low,High][Low, High]**[**L**o**w**,**H**i**g**h**]using logged sensor and estimated-state data |
| **Air humidity within target range (%)**                    | 60–70% of operating time                          | **≥ 85%**of operating time                                             | Compare humidity readings and filtered estimates against the target RH band over time                                                                                                                                        |
| **Temperature within target range (%)**                     | 65–75% of operating time                          | **≥ 90%**of operating time                                             | Time-series evaluation from sensor logs and dashboard records                                                                                                                                                                |
| **Mean absolute tracking error of soil moisture**           | 8–12% error                                       | **≤ 4%**error                                                          | Compute MAE between target/reference soil moisture and measured/estimated soil moisture over evaluation periods                                                                                                              |
| **Number of threshold violations per day**                  | 8–15 violations/day                               | **≤ 3 violations/day**                                           | Count how many times temperature, humidity, or soil moisture go below Low or above High limits                                                                                                                               |
| **Overshoot after control action**                          | Frequent; often > 10% beyond target band           | **≤ 5%**overshoot                                                      | Measure the maximum deviation above the target band after irrigation/misting/fan activation                                                                                                                                  |
| **Water usage per day**                                     | 100% reference of current manual/rule-based system | **Reduce by 15–25%**                                             | Compare total irrigation/misting duration or estimated water volume before and after HMPC deployment                                                                                                                         |
| **Energy usage of actuators**                               | 100% reference                                     | **Reduce by 10–20%**                                             | Estimate from fan/pump/misting runtime logs multiplied by actuator power ratings                                                                                                                                             |
| **Actuator switching frequency**                            | High, frequent ON/OFF chattering                   | **Reduce by 30–50%**                                             | Count the number of control state changes for pump, misting system, and fan per day                                                                                                                                          |
| **Prediction accuracy for next-step / short-horizon state** | Basic persistence or threshold logic only          | **RMSE improved by ≥ 20–30%**                                   | Compare HMPC prediction model outputs against actual future measurements overk+1,k+2,...k+1, k+2, ...**k**+**1**,**k**+**2**,**...**steps                                                            |
| **State estimation error after Adaptive Kalman filtering**  | Raw sensor noise remains unfiltered                | **Variance reduced by ≥ 30%**or estimation RMSE improved significantly | Compare raw sensor signal variance and filtered-state variance; if ground truth/reference is available, compute RMSE                                                                                                         |
| **Control decision response time**                          | Human-dependent or simple periodic response        | **< 2 s**for computation per control cycle                        | Measure elapsed time from receiving sensor/state data to generating the control action                                                                                                                                       |
| **System uptime / monitoring availability**                 | Intermittent or manual-only monitoring             | **≥ 95%**uptime during test period                                     | Measure percentage of time the ESP32 + broker + backend + dashboard remain operational                                                                                                                                       |
| **Data logging completeness**                               | Some data missing or not stored                    | **≥ 98%**data capture rate                                             | Compare expected sensor samples versus successfully stored records in InfluxDB/backend database                                                                                                                              |
| **Dashboard update latency**                                | Delayed/manual observation                         | **≤ 5 s**end-to-end delay                                        | Measure time from sensor reading generation to visualization in dashboard/Grafana                                                                                                                                            |
| **Successful automatic control rate**                       | 0% if system is manual                             | **≥ 90%**scheduled/required control actions executed correctly         | Check command logs versus actual actuator execution logs                                                                                                                                                                     |
| **Reduction in manual intervention**                        | Operators manually decide most actions             | **Reduce manual interventions by ≥ 70%**                         | Count the number of manual overrides or operator-triggered actions before and after deployment                                                                                                                               |

---

## 4. User Personas

### Persona: [Name, e.g., "Alex the Admin"]

- **Role**: [Job title or user type]
- **Goals**: [What they want to accomplish]
- **Pain points**: [Current frustrations this product addresses]
- **Technical level**: [Non-technical / Moderate / Developer]
- **Usage frequency**: [Daily / Weekly / Occasional]

### Persona: [Name, e.g., "Sam the End User"]

- **Role**: [Job title or user type]
- **Goals**: [What they want to accomplish]
- **Pain points**: [Current frustrations]
- **Technical level**: [Non-technical / Moderate / Developer]
- **Usage frequency**: [Daily / Weekly / Occasional]

---

## 5. Functional Requirements

> ### 5.1 Sensor Data Acquisition
>
> * **FR-001** : The system must collect real-time soil moisture readings from the greenhouse soil moisture sensor at a configurable sampling interval.
> * **FR-002** : The system must collect real-time air temperature readings from the greenhouse temperature sensor at a configurable sampling interval.
> * **FR-003** : The system must collect real-time relative humidity readings from the greenhouse humidity sensor at a configurable sampling interval.
> * **FR-004** : The system must collect real-time light intensity readings from the greenhouse light sensor at a configurable sampling interval.
> * **FR-005** : The system must timestamp every sensor reading at the moment it is received by the system.
> * **FR-006** : The system must associate each sensor reading with a unique device ID and greenhouse unit ID.
> * **FR-007** : The system must support configurable sampling times for each sensor stream independently.
> * **FR-008** : The system must support manual triggering of an immediate sensor read for diagnostic or calibration purposes.
>
> ---
>
> ### 5.2 Device Connectivity and Communication
>
> * **FR-009** : The system must support wireless communication between ESP32 nodes and the backend.
> * **FR-010** : The system must support MQTT as a communication protocol for sensor data transmission.
> * **FR-011** : The system must support WebSocket-based communication for real-time status updates when required.
> * **FR-012** : The system must reconnect automatically after temporary network interruption.
> * **FR-013** : The system must buffer unsent sensor messages locally when the connection is unavailable.
> * **FR-014** : The system must transmit buffered messages once the connection is restored.
> * **FR-015** : The system must verify whether a device is online, offline, or unstable based on heartbeat or message timeout.
> * **FR-016** : The system must log communication failures between edge devices and the backend.
>
> ---
>
> ### 5.3 Data Validation and Preprocessing
>
> * **FR-017** : The system must validate incoming sensor readings before using them in estimation or control.
> * **FR-018** : The system must detect missing sensor values.
> * **FR-019** : The system must detect out-of-range sensor values based on predefined valid bounds.
> * **FR-020** : The system must detect corrupted or malformed incoming sensor payloads.
> * **FR-021** : The system must mark invalid sensor readings with a validation status instead of silently discarding them.
> * **FR-022** : The system must support simple preprocessing operations such as scaling, normalization, and unit conversion before estimation.
> * **FR-023** : The system must support replacing a missing reading with the most recent valid value, interpolation, or another configured fallback policy.
> * **FR-024** : The system must record the preprocessing method applied to each adjusted data point.
>
> ---
>
> ### 5.4 Sensor Calibration and Health Monitoring
>
> * **FR-025** : The system must allow calibration parameters to be defined for each sensor.
> * **FR-026** : The system must apply sensor-specific calibration formulas before storing or using sensor values.
> * **FR-027** : The system must allow recalibration of sensors without changing application source code.
> * **FR-028** : The system must track when a sensor was last calibrated.
> * **FR-029** : The system must detect sensor drift when readings remain consistently biased or abnormal over time.
> * **FR-030** : The system must detect a stuck sensor condition when repeated values remain unchanged beyond a configurable threshold.
> * **FR-031** : The system must notify operators when a sensor is suspected to be unhealthy or requires recalibration.
>
> ---
>
> ### 5.5 State Estimation using Adaptive Kalman Filter
>
> * **FR-032** : The system must estimate the greenhouse state using an Adaptive Kalman Filter rather than relying only on raw sensor values.
> * **FR-033** : The state estimation module must use sensor measurements as observations in the estimation process.
> * **FR-034** : The state estimation module must produce filtered estimates for soil moisture.
> * **FR-035** : The state estimation module must produce filtered estimates for air temperature.
> * **FR-036** : The state estimation module must produce filtered estimates for relative humidity.
> * **FR-037** : The state estimation module must update the estimated state at every control cycle.
> * **FR-038** : The Adaptive Kalman module must adapt its noise-related parameters when measurement uncertainty changes over time.
> * **FR-039** : The Adaptive Kalman module must adapt its estimation behavior when process uncertainty changes over time.
> * **FR-040** : The system must preserve both raw measurements and filtered estimates for later comparison.
> * **FR-041** : The system must expose the current estimated state to the prediction and control modules.
> * **FR-042** : The system must log estimation residuals for diagnostic and evaluation purposes.
>
> ---
>
> ### 5.6 Prediction Modeling
>
> * **FR-043** : The system must predict future greenhouse states over a finite prediction horizon.
> * **FR-044** : The system must support ARX as a valid prediction model option.
> * **FR-045** : The system must allow replacement of ARX with another selected predictive model without redesigning the full system.
> * **FR-046** : The prediction module must use current estimated state values as model inputs.
> * **FR-047** : The prediction module must support the use of past sensor/state history as model input.
> * **FR-048** : The prediction module must forecast soil moisture for future steps k+1…k+Hk+1 \dots k+H**k**+**1**…**k**+**H**.
> * **FR-049** : The prediction module must forecast air temperature for future steps k+1…k+Hk+1 \dots k+H**k**+**1**…**k**+**H**.
> * **FR-050** : The prediction module must forecast relative humidity for future steps k+1…k+Hk+1 \dots k+H**k**+**1**…**k**+**H**.
> * **FR-051** : The prediction module must support exogenous inputs such as light intensity or actuator actions when used by the selected model.
> * **FR-052** : The system must retain prediction outputs for each control cycle for later evaluation.
> * **FR-053** : The system must calculate and store prediction error after actual future measurements become available.
>
> ---
>
> ### 5.7 Hybrid Model Predictive Control (HMPC)
>
> * **FR-054** : The system must implement Hybrid Model Predictive Control to determine control actions over a future horizon.
> * **FR-055** : The HMPC module must use estimated current state as the initial state for optimization.
> * **FR-056** : The HMPC module must use predicted future system evolution when selecting control actions.
> * **FR-057** : The HMPC module must optimize multiple objectives in a single control cycle.
> * **FR-058** : The HMPC module must minimize deviation of soil moisture from its desired operating range.
> * **FR-059** : The HMPC module must minimize deviation of air temperature from its desired operating range.
> * **FR-060** : The HMPC module must minimize deviation of relative humidity from its desired operating range.
> * **FR-061** : The HMPC module must penalize excessive water use.
> * **FR-062** : The HMPC module must penalize excessive energy use.
> * **FR-063** : The HMPC module must penalize excessive actuator switching or large control variation between consecutive steps.
> * **FR-064** : The HMPC module must support a configurable prediction horizon.
> * **FR-065** : The HMPC module must support a configurable control horizon.
> * **FR-066** : The HMPC module must apply only the first control action of the optimized sequence at each time step.
> * **FR-067** : The HMPC module must repeat the optimization process at the next sampling step according to the receding horizon principle.
>
> ---
>
> ### 5.8 Control Constraints and Hybrid Action Space
>
> * **FR-068** : The controller must support lower and upper bounds for each actuator.
> * **FR-069** : The controller must support discrete or bounded irrigation durations.
> * **FR-070** : The controller must support discrete or bounded misting durations.
> * **FR-071** : The controller must support binary fan switching actions where applicable.
> * **FR-072** : The controller must respect minimum and maximum allowable durations for pump activation.
> * **FR-073** : The controller must respect minimum and maximum allowable durations for misting activation.
> * **FR-074** : The controller must respect safe operating ranges for greenhouse variables during optimization.
> * **FR-075** : The controller must handle hybrid system behavior that combines continuous environmental states and discrete or bounded actuator actions.
> * **FR-076** : The controller must reject infeasible control sequences that violate system constraints.
> * **FR-077** : The controller must fall back to a safe default action when no feasible optimization solution is found.
>
> ---
>
> ### 5.9 Actuator Control Execution
>
> * **FR-078** : The system must send irrigation commands to the pump actuator.
> * **FR-079** : The system must send misting commands to the mist actuator.
> * **FR-080** : The system must send ventilation commands to the fan actuator.
> * **FR-081** : The system must support automatic execution of controller-generated actions.
> * **FR-082** : The system must record when a control command is issued.
> * **FR-083** : The system must record whether an actuator acknowledged or executed the command when feedback is available.
> * **FR-084** : The system must detect actuator non-response when a command is not acknowledged within a configured timeout.
> * **FR-085** : The system must retry failed control commands based on a configured retry policy.
> * **FR-086** : The system must stop retrying and mark the command as failed after the retry limit is reached.
> * **FR-087** : The system must log every actuator execution result for traceability.
>
> ---
>
> ### 5.10 Manual Control and Override
>
> * **FR-088** : The system must support manual override for the irrigation pump.
> * **FR-089** : The system must support manual override for the misting system.
> * **FR-090** : The system must support manual override for the ventilation fan.
> * **FR-091** : The system must allow authorized users to switch between automatic mode and manual mode.
> * **FR-092** : The system must suspend automatic control for an actuator while that actuator is under manual override.
> * **FR-093** : The system must continue monitoring and logging data even when manual override is active.
> * **FR-094** : The system must record who initiated manual override and when it occurred.
> * **FR-095** : The system must record the duration of each manual override session.
> * **FR-096** : The system must support returning control from manual mode back to automatic mode without restarting the whole system.
>
> ---
>
> ### 5.11 Safety Rules and Fallback Logic
>
> * **FR-097** : The system must support safety rules independent of the HMPC optimizer.
> * **FR-098** : The system must prevent pump activation when soil moisture already exceeds a configured upper threshold.
> * **FR-099** : The system must prevent misting activation when relative humidity already exceeds a configured upper threshold.
> * **FR-100** : The system must support forced fan activation when temperature exceeds a configured emergency limit.
> * **FR-101** : The system must support forced fan activation when humidity exceeds a configured emergency limit.
> * **FR-102** : The system must enforce cooldown periods between repeated actuator activations when required.
> * **FR-103** : The system must switch to a safe fallback control strategy when the estimation or control module becomes unavailable.
> * **FR-104** : The fallback strategy must be configurable as threshold-based control, manual hold, or actuator-off mode.
> * **FR-105** : The system must record each time a safety rule overrides the HMPC decision.
> * **FR-106** : The system must notify users when fallback mode is entered or exited.
>
> ---
>
> ### 5.12 Monitoring Dashboard
>
> * **FR-107** : The system must provide a dashboard showing the latest greenhouse sensor readings.
> * **FR-108** : The dashboard must show the latest filtered state estimates.
> * **FR-109** : The dashboard must show predicted future trajectories for key environmental variables.
> * **FR-110** : The dashboard must show the current status of each actuator.
> * **FR-111** : The dashboard must show whether the system is currently in automatic mode, manual mode, or fallback mode.
> * **FR-112** : The dashboard must display whether each device is online or offline.
> * **FR-113** : The dashboard must show recent alerts and faults.
> * **FR-114** : The dashboard must refresh near real time without requiring full page reload.
> * **FR-115** : The dashboard must allow users to select a time range for viewing historical trends.
> * **FR-116** : The dashboard must support separate charts for raw measurements and filtered estimates.
> * **FR-117** : The dashboard must support overlaying predicted values with actual measured values for comparison.
>
> ---
>
> ### 5.13 Historical Data and Trend Visualization
>
> * **FR-118** : The system must store historical sensor data for long-term review.
> * **FR-119** : The system must store historical filtered state estimates for long-term review.
> * **FR-120** : The system must store historical prediction outputs for long-term review.
> * **FR-121** : The system must store historical actuator commands and execution results.
> * **FR-122** : The dashboard must allow users to visualize historical soil moisture trends.
> * **FR-123** : The dashboard must allow users to visualize historical temperature trends.
> * **FR-124** : The dashboard must allow users to visualize historical humidity trends.
> * **FR-125** : The dashboard must allow users to visualize historical actuator activity over time.
> * **FR-126** : The dashboard must allow comparison between raw data and filtered data over selected time windows.
> * **FR-127** : The dashboard must allow comparison between predicted trajectories and actual outcomes for selected time windows.
>
> ---
>
> ### 5.14 Alerts and Notifications
>
> * **FR-128** : The system must generate an alert when soil moisture drops below a configured lower threshold.
> * **FR-129** : The system must generate an alert when soil moisture exceeds a configured upper threshold.
> * **FR-130** : The system must generate an alert when temperature drops below a configured lower threshold.
> * **FR-131** : The system must generate an alert when temperature exceeds a configured upper threshold.
> * **FR-132** : The system must generate an alert when relative humidity drops below a configured lower threshold.
> * **FR-133** : The system must generate an alert when relative humidity exceeds a configured upper threshold.
> * **FR-134** : The system must generate an alert when a sensor becomes unavailable or unhealthy.
> * **FR-135** : The system must generate an alert when an actuator fails to execute a control command.
> * **FR-136** : The system must generate an alert when the system enters fallback mode.
> * **FR-137** : The system must support alert acknowledgment by an authorized user.
> * **FR-138** : The system must retain a history of generated alerts and acknowledgments.
>
> ---
>
> ### 5.15 Configuration and Tuning
>
> * **FR-139** : The system must allow users to configure target operating ranges for soil moisture.
> * **FR-140** : The system must allow users to configure target operating ranges for temperature.
> * **FR-141** : The system must allow users to configure target operating ranges for relative humidity.
> * **FR-142** : The system must allow users to configure Low and High thresholds separately from nominal target values when needed.
> * **FR-143** : The system must allow users to configure sampling time.
> * **FR-144** : The system must allow users to configure prediction horizon.
> * **FR-145** : The system must allow users to configure control horizon.
> * **FR-146** : The system must allow users to configure HMPC objective weights.
> * **FR-147** : The system must allow users to configure estimation-related parameters for the Adaptive Kalman module.
> * **FR-148** : The system must allow users to configure fallback policies and safety thresholds.
> * **FR-149** : The system must preserve configuration history when settings are changed.
> * **FR-150** : The system must record who changed a configuration and when the change occurred.
>
> ---
>
> ### 5.16 Data Storage and Export
>
> * **FR-151** : The system must store sensor data in a persistent database.
> * **FR-152** : The system must store filtered state data in a persistent database.
> * **FR-153** : The system must store prediction outputs in a persistent database.
> * **FR-154** : The system must store control decisions in a persistent database.
> * **FR-155** : The system must store alerts, faults, and override events in a persistent database.
> * **FR-156** : The system must support exporting selected historical data to CSV.
> * **FR-157** : The system must support exporting selected historical data to Excel or another structured report-friendly format.
> * **FR-158** : The system must support exporting logs for offline analysis.
> * **FR-159** : The system must support filtering export content by time range.
> * **FR-160** : The system must support filtering export content by sensor, variable, actuator, or event type.
>
> ---
>
> ### 5.17 User Roles and Access Control
>
> * **FR-161** : The system must support authenticated access for authorized users.
> * **FR-162** : The system must support at least an administrator role.
> * **FR-163** : The system must support at least an operator role.
> * **FR-164** : The system must support at least a read-only viewer role.
> * **FR-165** : The administrator role must be able to change system configuration.
> * **FR-166** : The operator role must be able to view data, acknowledge alerts, and use manual override where permitted.
> * **FR-167** : The viewer role must be able to monitor the dashboard without modifying control settings.
> * **FR-168** : The system must restrict manual override and configuration changes to authorized roles only.
> * **FR-169** : The system must record login, logout, and critical user actions for audit purposes.
>
> ---
>
> ### 5.18 Fault Detection and Diagnostics
>
> * **FR-170** : The system must detect sensor communication loss.
> * **FR-171** : The system must detect actuator communication loss.
> * **FR-172** : The system must detect repeated estimation failures.
> * **FR-173** : The system must detect repeated optimization failures.
> * **FR-174** : The system must classify faults by type such as sensor fault, communication fault, actuator fault, or control-module fault.
> * **FR-175** : The system must expose the current fault status on the dashboard.
> * **FR-176** : The system must maintain a fault history log.
> * **FR-177** : The system must support basic diagnostic details showing why a command, prediction, or optimization cycle failed.
>
> ---
>
> ### 5.19 Experimentation and Evaluation Support
>
> * **FR-178** : The system must support running the controller under different parameter sets for experimentation.
> * **FR-179** : The system must support comparing performance across different controller weight settings.
> * **FR-180** : The system must support comparing raw-sensor control performance against Adaptive-Kalman-based control performance.
> * **FR-181** : The system must support comparing threshold-based control against HMPC-based control performance.
> * **FR-182** : The system must calculate time-in-target-range metrics for each environmental variable.
> * **FR-183** : The system must calculate total water use over a selected evaluation period.
> * **FR-184** : The system must calculate actuator switching count over a selected evaluation period.
> * **FR-185** : The system must calculate prediction error metrics such as MAE or RMSE.
> * **FR-186** : The system must calculate estimation improvement indicators such as variance reduction or residual statistics.
> * **FR-187** : The system must support exporting experiment results for inclusion in reports or presentations.
>
> ---
>
> ### 5.20 Auditability and Traceability
>
> * **FR-188** : The system must log the full control decision context for each cycle, including raw measurements, filtered state, predicted trajectory, selected action, and execution result.
> * **FR-189** : The system must allow users to trace from an actuator action back to the control cycle that produced it.
> * **FR-190** : The system must allow users to trace from an alert back to the sensor reading, estimated state, or rule violation that triggered it.
> * **FR-191** : The system must preserve model version or controller version metadata when predictions or control decisions are generated.
> * **FR-192** : The system must preserve configuration version metadata when a control decision is generated.
> * **FR-193** : The system must support viewing historical decisions together with the parameter settings active at that time.

---

## 6. Non-Functional Requirements

## 7. Out of Scope (v1.0)

## 6.1 Performance

* **NFR-001** : The system must ingest sensor data from greenhouse devices with an average end-to-end delay of **≤ 2 seconds** under normal operating conditions.
* **NFR-002** : The dashboard must reflect newly received sensor values within **≤ 5 seconds** under normal network conditions.
* **NFR-003** : The state estimation module must complete one Adaptive Kalman update cycle within **≤ 500 ms** after receiving new sensor data.
* **NFR-004** : The HMPC control computation for one control cycle must complete within **≤ 2 seconds** under normal operating conditions.
* **NFR-005** : The total time from receiving new sensor data to issuing a control command must be **≤ 5 seconds** in automatic mode.
* **NFR-006** : Alert generation for critical threshold violations must occur within **≤ 3 seconds** after the triggering condition is detected.
* **NFR-007** : Historical data queries for a selected 24-hour period must return results within **≤ 3 seconds** under normal load.
* **NFR-008** : Exporting one day of greenhouse sensor and actuator logs must complete within **≤ 10 seconds** for normal dataset sizes.
* **NFR-009** : The system must support continuous operation at the configured sampling interval without dropping more than **2%** of expected sensor samples over a 24-hour period.
* **NFR-010** : The system must maintain stable performance when simultaneously processing real-time sensing, estimation, prediction, dashboard updates, and control logging for at least one greenhouse prototype unit.

---

## 6.2 Security

* **NFR-011** : Authentication must be required for all non-public web, dashboard, and configuration endpoints.
* **NFR-012** : The system must implement role-based access control for administrator, operator, and viewer roles.
* **NFR-013** : Only authorized roles may change control parameters, trigger manual override, or modify safety settings.
* **NFR-014** : All user passwords must be stored using a strong one-way password hashing algorithm and must never be stored in plaintext.
* **NFR-015** : All communication between user-facing web clients and backend services must be protected using HTTPS/TLS in deployment environments.
* **NFR-016** : Device-to-server communication should use secure transport where deployment constraints allow it.
* **NFR-017** : Sensitive configuration values such as database credentials, broker credentials, API secrets, and tokens must be stored outside source code using environment variables or an equivalent secret-management mechanism.
* **NFR-018** : The system must validate and sanitize all incoming API, dashboard, and device payloads to reduce injection and malformed-input risks.
* **NFR-019** : The system must log authentication attempts, configuration changes, manual override events, and safety-critical actions for audit purposes.
* **NFR-020** : The system must terminate or invalidate sessions after a configurable inactivity timeout.
* **NFR-021** : The system must protect against common web vulnerabilities relevant to the stack, including broken authentication, insecure direct object access, and input-based attacks.
* **NFR-022** : Backup files and exported logs containing operational data must be accessible only to authorized users.

---

## 6.3 Scalability

* **NFR-023** : The architecture must support at least **1 greenhouse prototype** with multiple sensors and actuators operating continuously.
* **NFR-024** : The architecture should be extensible to support at least **10 greenhouse units** without major redesign of the communication, storage, and monitoring layers.
* **NFR-025** : The system must support adding new sensor streams without requiring redesign of the entire backend data pipeline.
* **NFR-026** : The system must support adding new actuator types without requiring redesign of the entire dashboard and logging model.
* **NFR-027** : The data storage layer must support growth in historical time-series data for long-duration experiments.
* **NFR-028** : The system should allow prediction and control modules to be upgraded or replaced independently from the sensing and dashboard modules.
* **NFR-029** : The communication layer must support concurrent data ingestion from multiple edge devices without message collisions causing system failure.
* **NFR-030** : The system should remain functionally correct when sampling frequency, prediction horizon, or number of tracked variables increases within prototype-scale limits.

---

## 6.4 Accessibility

* **NFR-031** : All primary dashboard functions must be usable without relying solely on color to convey meaning.
* **NFR-032** : Charts, alerts, and actuator states must include text labels or legends in addition to visual color indicators.
* **NFR-033** : User-facing text must maintain sufficient contrast against the background for clear readability.
* **NFR-034** : The dashboard must support keyboard navigation for primary actions such as viewing metrics, changing time ranges, and acknowledging alerts.
* **NFR-035** : Interactive controls such as buttons, toggles, and form fields must have clearly visible labels.
* **NFR-036** : The interface should remain usable on laptop and desktop screens commonly used in classrooms, labs, and control rooms.
* **NFR-037** : The system should use clear, non-ambiguous wording for alerts, faults, actuator modes, and safety states.
* **NFR-038** : Time-series charts and tables should remain readable when displayed at reduced window sizes used on smaller devices.

---

## 6.5 Browser / Platform Support

* **NFR-039** : The web dashboard must support recent stable versions of  **Chrome, Edge, and Firefox** .
* **NFR-041** : The dashboard must be responsive down to a viewport width of **375 px** for mobile monitoring use.
* **NFR-042** : The system must support deployment of the backend on common Linux-based server environments.
* **NFR-043** : The edge-device software must support ESP32-class microcontrollers used in the greenhouse prototype.
* **NFR-044** : The operator dashboard must remain usable on desktop operating systems commonly used by the team, including Windows.
* **NFR-045** : The system must not require high-end hardware for normal monitoring and prototype-scale control operation.

---

## 6.6 Reliability

* **NFR-046** : The system must achieve **≥ 95% uptime** during prototype testing periods, excluding planned maintenance.
* **NFR-047** : The system must automatically recover from temporary network interruptions without requiring a full system restart.
* **NFR-048** : The system must preserve previously stored data when a device disconnects unexpectedly.
* **NFR-049** : The system must continue operating in monitoring mode even if automatic control is temporarily unavailable.
* **NFR-050** : The system must enter a safe fallback mode when the HMPC optimizer fails repeatedly or becomes unavailable.
* **NFR-051** : The system must enter a safe fallback mode when critical sensor data becomes unavailable for longer than a configured timeout.
* **NFR-052** : Automated backups of persistent operational data must occur at least once every **24 hours** during active deployment periods.
* **NFR-053** : The system must retain sufficient logs to diagnose failures in sensing, communication, estimation, prediction, and actuation.
* **NFR-054** : A failed actuator command must not crash the overall monitoring and dashboard system.
* **NFR-055** : The system must preserve configuration settings across restart unless an authorized user explicitly changes them.

---

## 6.7 Maintainability

* **NFR-056** : The system must be modular enough that sensing, estimation, prediction, control, storage, and dashboard components can be maintained independently.
* **NFR-057** : Configuration values such as thresholds, horizons, and controller weights must be changeable without modifying core source code.
* **NFR-058** : The codebase must include sufficient internal documentation for future team members to understand major modules and data flow.
* **NFR-059** : Logs and diagnostics must be structured so that failures can be traced to specific modules or control cycles.
* **NFR-060** : The system should support replacing the prediction model or tuning the controller without redesigning the rest of the architecture.
* **NFR-061** : Database schema and logging structures must support future expansion of sensors, actuators, and experiment metadata.
* **NFR-062** : The system should separate prototype-specific logic from reusable platform logic wherever practical.

---

## 6.8 Observability and Auditability

* **NFR-063** : The system must maintain timestamped logs for sensor ingestion, filtered-state generation, prediction output, control decision, and actuator execution.
* **NFR-064** : The system must allow operators to trace a control action back to the associated state estimate and prediction cycle.
* **NFR-065** : The system must allow operators to trace an alert back to the triggering measurement, estimate, or rule condition.
* **NFR-066** : The system must retain audit history for manual override actions, configuration changes, and acknowledgment of alerts.
* **NFR-067** : The system should preserve controller version and configuration version metadata for experiment reproducibility.

---

## 6.9 Data Quality

* **NFR-068** : The system must preserve raw sensor data separately from filtered or estimated data.
* **NFR-069** : The system must mark invalid, interpolated, or corrected data points clearly in storage and exports.
* **NFR-070** : Time synchronization across devices and backend components must be accurate enough to support consistent sequence analysis of sensing and control events.
* **NFR-071** : Stored data must be sufficiently complete to support later evaluation of HMPC performance, prediction error, and Kalman filtering effectiveness.
* **NFR-072** : Exported datasets must contain timestamps, variable names, units, and source identifiers to support offline analysis.

---

---

## 8. Open Questions

Not have

## 9. Revision History

> Human entries only. Agents do not modify this section.

| Date         | Author | Change Description |
| ------------ | ------ | ------------------ |
| [YYYY-MM-DD] | [Name] | Initial draft      |
