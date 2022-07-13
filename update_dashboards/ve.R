#!/usr/bin/env Rscript

# script is intended for running from base dir `/logistics`
# normalizePath(".")

rm(list = ls())
suppressPackageStartupMessages({
  library(tidyverse)
  library(cdcfluview)
  library(zoo)
  library(boot)
  library(epitools)
})

"%notin%" <- Negate("%in%")

# setwd("C:\\Users\\Cooper Marshall\\code\\logistics")
# setwd("C:/Users/hansencl/Desktop/VE dashboard final")
# Exclusion Criteria
# Must be King County
# Must be Community Enrollment
# Must have a test result
# Must be over 12 - (vaccines extended to 5yrs and up on November 2)
# date_last_covid_dose must be after 2020-12-01 and before the encountered date


# Prep Data ------------------------------------------------------
other_vax <- c("astrazeneca", "dont_know", "dont_say", "novavax", "other")
dat <- read.csv("data/id3c_scan_vaccine_data.csv") %>%
  # dat <- read.csv("ve_dashboard_with_raw_crts_2022-07-13T05_53_07.631427-07_00.csv") %>%
  mutate(
    s_gene_crt_1 = as.numeric(s_gene_crt_1),
    s_gene_crt_2 = as.numeric(s_gene_crt_2),
    orf1b_crt_1 = as.numeric(orf1b_crt_1),
    orf1b_crt_2 = as.numeric(orf1b_crt_2)
  ) %>%
  filter(
    encountered >= "2021-01-20" &
      enrollment_method == "Community Enrollment" &
      date_last_covid_dose <= encountered &
      age >= 12 &
      (region == "South King County" | region == "North King County"),
    vac_name_1 %notin% other_vax, vac_name_2 %notin% other_vax, vac_name_3 %notin% other_vax
  ) %>%
  mutate(
    encountered = as.Date(encountered),
    date_last_covid_dose = as.Date(date_last_covid_dose),
    mmwr_week(encountered),
    week_date = mmwr_week_to_date(mmwr_year, mmwr_week),
    week_num = dense_rank(week_date),
    case_control = factor(hcov19_result, levels = c("Positive", "Inconclusive", "Negetive"), labels = c("case", "case", "control")),
    case_control_bin = ifelse(hcov19_result == "Positive" | hcov19_result == "Inconclusive", 1,
      ifelse(hcov19_result == "Negetive", 0, NA)
    ),
    s_mean = rowMeans(.[, c("s_gene_crt_1", "s_gene_crt_2")], na.rm = TRUE),
    orf_mean = rowMeans(.[, c("orf1b_crt_1", "orf1b_crt_2")], na.rm = TRUE),
    mean_diff = abs(orf_mean - s_mean),
    delta_case = ifelse(orf_mean <= 30 & (mean_diff > 6 | is.nan(s_mean)) & encountered >= "2021-06-01", 1, 0),
    omicron_case = ifelse(orf_mean < 33 & mean_diff <= 3 & !is.na(orf1b_crt_1) & !is.na(orf1b_crt_2) & !is.na(s_gene_crt_1) & !is.na(s_gene_crt_2) & encountered >= "2021-12-01", 1, 0),
    alpha = ifelse(encountered >= "2021-04-11" & encountered < "2021-06-20", 1, 0),
    delta = ifelse(encountered >= "2021-06-20" & encountered < "2021-12-12", 1, 0),
    omicron = ifelse(encountered >= "2021-12-12" & encountered <= Sys.Date(), 1, 0),
    variant_indicator = factor(ifelse(delta == 1, "delta",
      ifelse(omicron == 1, "omicron", "pre_delta")
    ), levels = c("pre_delta", "delta", "omicron")),
    prior_infection = ifelse(grepl("yes", prior_test_positive), 1, 0),
    time_since_vax = as.numeric(difftime(encountered, date_last_covid_dose, units = "days")),
    doses_recode = ifelse(covid_doses == "2" & (time_since_vax >= 180), "2_doses_>6m",
      ifelse(covid_doses == "2" & time_since_vax < 180, "2_doses_<6m",
        ifelse(covid_doses == "1", "1_dose",
          ifelse(covid_doses == "", "unknown", paste(covid_doses, "_doses", sep = ""))
        )
      )
    ),
    doses_recode = factor(doses_recode, levels = c("unknown", "0_doses", "1_dose", "2_doses_>6m", "2_doses_<6m", "3_doses")),
    regression_doses = factor(doses_recode,
      levels = c("0_doses", "1_dose", "2_doses_>6m", "2_doses_<6m", "3_doses"),
      labels = c("reference", "reference", "2_doses_>6m", "2_doses_<6m", "3_doses")
    ), # combining unknown, 0 and 1 doses
    vax_status = ifelse(vaccination_status == "not_vaccinated" | vaccination_status == "partially_vaccinated" | vaccination_status == "unknown" | vaccination_status == "na" | vaccination_status == "invalid", "not_fully", vaccination_status),
    vax_status = factor(vax_status, levels = c("not_fully", "fully_vaccinated", "boosted")),
    sex = factor(sex, levels = c("female", "male")),
    race_ethnicity_recode = factor(race_ethnicity,
      levels = c(
        "White, not Hispanic", "Asian, not Hispanic", "Black, not Hispanic", "Hispanic or Latino, any Race",
        "Amer. Indian or Alaska Native", "NH/OPI", "Other/Multi, Non Hisp.", ""
      ),
      labels = c("White", "Asian", "Black", "Hispanic", "Other", "Other", "Other", "Other")
    ),
    age_group = ifelse(age >= 12 & age < 25, "age_12_to_25",
      ifelse(age >= 25 & age < 35, "age_25_to_35",
        ifelse(age >= 35 & age < 50, "age_35_to_50", "over_50")
      )
    )
  ) %>%
  filter(!is.na(case_control), vaccination_status != "unknown", vaccination_status != "na", vaccination_status != "invalid")

# write.csv(dat, "data/dat.csv")

# SCAN participants by vaccine doses  --------------------------------

scan_vax_dose <- dat %>%
  group_by(week_date, doses_recode) %>%
  tally() %>%
  ungroup() %>%
  mutate(
    doses_recode = as.character(doses_recode),
    doses_recode = ifelse(is.na(doses_recode), "unknown", doses_recode),
    doses_recode = factor(doses_recode,
      levels = c("3_doses", "2_doses_<6m", "2_doses_>6m", "1_dose", "0_doses", "unknown"),
      labels = c("3 Doses", "2 Doses <6m ago", "2 Doses >6m ago", "1 Dose", "0 Doses", "Unknown")
    )
  )

write.csv(scan_vax_dose, "data/vaccine_doses.csv", row.names = F)
# These dataframe is used to make the vaccine doses over time plot

scan_vax_status <- dat %>%
  group_by(week_date, vax_status) %>%
  tally() %>%
  ungroup() %>%
  pivot_wider(names_from = vax_status, values_from = n) %>%
  replace(is.na(.), 0) %>%
  mutate(
    not_roll = rollapplyr(rowSums(.[, 2]), 9, sum, partial = TRUE),
    fully_roll = rollapplyr(rowSums(.[, 3]), 9, sum, partial = TRUE),
    boost_roll = rollapplyr(rowSums(.[, 4]), 9, sum, partial = TRUE),
    total = not_roll + fully_roll + boost_roll,
    prop_not = not_roll / total,
    prop_fully = fully_roll / total,
    prop_boost = boost_roll / total
  ) %>%
  pivot_longer(cols = c(prop_not, prop_fully, prop_boost), names_to = "status", values_to = "prop") %>%
  select(week_date, status, prop)

write.csv(scan_vax_status, "data/vaccination_status.csv", row.names = F)
# This dataframe is used to make the vaccination status over time plot (bottom plot tab 1)


# Proportion positive over time by vaccination status ---------------------
prop_groups <- dat %>%
  filter(week_date >= "2021-04-01", !is.na(vax_status)) %>%
  group_by(week_date, case_control, vax_status) %>%
  tally() %>%
  ungroup() %>%
  pivot_wider(id_cols = week_date, names_from = c(case_control, vax_status), values_from = n) %>%
  replace(is.na(.), 0) %>%
  # summing over 6-week windows
  mutate(
    risk_notfully = rollapplyr(case_not_fully, 9, sum, partial = TRUE) / (rollapplyr(case_not_fully, 9, sum, partial = TRUE) + rollapplyr(control_not_fully, 9, sum, partial = TRUE)),
    risk_fully_vaccinated = rollapplyr(case_fully_vaccinated, 9, sum, partial = TRUE) / (rollapplyr(case_fully_vaccinated, 9, sum, partial = TRUE) + rollapplyr(control_fully_vaccinated, 9, sum, partial = TRUE)),
    risk_boosted = rollapplyr(case_boosted, 9, sum, partial = TRUE) / (rollapplyr(case_boosted, 9, sum, partial = TRUE) + rollapplyr(control_boosted, 9, sum, partial = TRUE))
  ) %>%
  select(week_date, risk_notfully, risk_fully_vaccinated, risk_boosted) %>%
  pivot_longer(!week_date, names_to = "Vaccination Status", values_to = "Risk")
write.csv(prop_groups, "data/infection_probability.csv", row.names = F)


# Screening Method - DATA prep--------------------------------------------------------

# with bootstrapped CIs

# function for bootstrapping the fully v not fully categories

boot_fully_v_not <- function(data, indices) {
  screening <- data[indices, ] %>%
    group_by(case_control, vax_status) %>%
    tally() %>%
    ungroup() %>%
    pivot_wider(names_from = c(case_control, vax_status), values_from = n) %>%
    replace(is.na(.), 0) %>%
    mutate(
      ppv = (case_fully_vaccinated + control_fully_vaccinated) / (rowSums(.)),
      pcv = case_fully_vaccinated / (case_fully_vaccinated + case_not_fully),
      ve = 1 - ((pcv / (1 - pcv)) * ((1 - ppv) / ppv)),
      or = 1 - ve,
      p = case_not_fully / (case_not_fully + control_not_fully),
      rel_risk = 1 / (or / (1 - p + (p * or)))
    )
  ve <- screening$ve
  rel_risk <- screening$rel_risk
  return(c(ve, rel_risk))
}

# function to format results - for fully v not fully function
boot_results_1 <- function(data, boot_data) {
  screening_data <- data %>%
    group_by(case_control, vax_status) %>%
    tally() %>%
    ungroup() %>%
    pivot_wider(names_from = c(case_control, vax_status), values_from = n) %>%
    replace(is.na(.), 0) %>%
    mutate(
      ppv = (case_fully_vaccinated + control_fully_vaccinated) / (rowSums(.)),
      ppuv = 1 - ppv,
      pcv = case_fully_vaccinated / (case_fully_vaccinated + case_not_fully),
      pcuv = 1 - pcv,
      ve = (1 - ((pcv / (1 - pcv)) * ((1 - ppv) / ppv))),
      ve_lower = as.numeric(quantile(boot_data$t[, 1], .025)),
      ve_upper = as.numeric(quantile(boot_data$t[, 1], .975)),
      or = 1 - ve,
      p = case_not_fully / (case_not_fully + control_not_fully),
      rel_risk = 1 / (or / (1 - p + (p * or))),
      rel_risk_lower = as.numeric(quantile(boot_data$t[, 2], .025)),
      rel_risk_upper = as.numeric(quantile(boot_data$t[, 2], .975))
    )
}

# make new function for boosted v fully vaccinated
boot_boost_v_fully <- function(data, indices) {
  screening <- data[indices, ] %>%
    group_by(case_control, vax_status) %>%
    tally() %>%
    ungroup() %>%
    pivot_wider(names_from = c(case_control, vax_status), values_from = n) %>%
    replace(is.na(.), 0) %>%
    mutate(
      ppv = (case_boosted + control_boosted) / (rowSums(.)),
      pcv = case_boosted / (case_fully_vaccinated + case_boosted),
      ve = 1 - ((pcv / (1 - pcv)) * ((1 - ppv) / ppv)),
      or = 1 - ve,
      p = case_fully_vaccinated / (case_fully_vaccinated + control_fully_vaccinated),
      rel_risk = 1 / (or / (1 - p + (p * or)))
    )
  ve <- screening$ve
  rel_risk <- screening$rel_risk
  return(c(ve, rel_risk))
}

# function to format results - for boosted v fully function
boot_results_2 <- function(data, boot_data) {
  screening_data <- data %>%
    group_by(case_control, vax_status) %>%
    tally() %>%
    ungroup() %>%
    pivot_wider(names_from = c(case_control, vax_status), values_from = n) %>%
    replace(is.na(.), 0) %>%
    mutate(
      ppv = (case_boosted + control_boosted) / (rowSums(.)),
      ppuv = 1 - ppv,
      pcv = case_boosted / (case_fully_vaccinated + case_boosted),
      pcuv = 1 - pcv,
      ve = (1 - ((pcv / (1 - pcv)) * ((1 - ppv) / ppv))),
      ve_lower = as.numeric(quantile(boot_data$t[, 1], .025)),
      ve_upper = as.numeric(quantile(boot_data$t[, 1], .975)),
      or = 1 - ve,
      p = case_fully_vaccinated / (case_fully_vaccinated + control_fully_vaccinated),
      rel_risk = 1 / (or / (1 - p + (p * or))),
      rel_risk_lower = as.numeric(quantile(boot_data$t[, 2], .025)),
      rel_risk_upper = as.numeric(quantile(boot_data$t[, 2], .975))
    )
}

# run function with bootstrapping for pre delta period
boot_predelta <- boot(dat %>% filter(week_date >= "2021-04-01", !is.na(vax_status), variant_indicator == "pre_delta"), boot_fully_v_not, R = 1000)
results_predelta <- boot_results_1(dat %>% filter(week_date >= "2021-04-01", !is.na(vax_status), variant_indicator == "pre_delta"), boot_predelta) %>%
  mutate(comparison = "Fully Vaccinated vs. Not Fully Vaccinated", period = "Pre-Delta") %>%
  select(comparison, period, ppv, ppuv, pcv, pcuv, ve, ve_lower, ve_upper, rel_risk, rel_risk_lower, rel_risk_upper)

# run function with bootstrapping for delta period
boot_delta <- boot(dat %>% filter(!is.na(vax_status), variant_indicator == "delta", vax_status != "boosted"), boot_fully_v_not, R = 1000)
results_delta <- boot_results_1(dat %>% filter(!is.na(vax_status), variant_indicator == "delta", vax_status != "boosted"), boot_delta) %>%
  mutate(comparison = "Fully Vaccinated vs. Not Fully Vaccinated", period = "Delta") %>%
  select(comparison, period, ppv, ppuv, pcv, pcuv, ve, ve_lower, ve_upper, rel_risk, rel_risk_lower, rel_risk_upper)

# run function with bootstrapping for omicron period
boot_omicron <- boot(dat %>% filter(!is.na(vax_status), variant_indicator == "omicron", vax_status != "boosted"), boot_fully_v_not, R = 1000)
results_omicron <- boot_results_1(dat %>% filter(!is.na(vax_status), variant_indicator == "omicron", vax_status != "boosted"), boot_omicron) %>%
  mutate(comparison = "Fully Vaccinated vs. Not Fully Vaccinated", period = "Omicron") %>%
  select(comparison, period, ppv, ppuv, pcv, pcuv, ve, ve_lower, ve_upper, rel_risk, rel_risk_lower, rel_risk_upper)

# run boosted v fully with bootstraps for omicron - not this uses different functions
boot_omicron.2 <- boot(dat %>% filter(!is.na(vax_status), variant_indicator == "omicron", vax_status != "not_fully"), boot_boost_v_fully, R = 1000)
results_omicron.2 <- boot_results_2(dat %>% filter(!is.na(vax_status), variant_indicator == "omicron", vax_status != "not_fully"), boot_omicron.2) %>%
  mutate(comparison = "Boosted vs. Fully Vaccinated", period = "Omicron") %>%
  select(comparison, period, ppv, ppuv, pcv, pcuv, ve, ve_lower, ve_upper, rel_risk, rel_risk_lower, rel_risk_upper)


screening_data <- rbind(results_predelta, results_delta, results_omicron, results_omicron.2) %>%
  mutate(period = factor(period, levels = c("Pre-Delta", "Delta", "Omicron")))

write.csv(screening_data, "data/screening_method.csv", row.names = F)


# Run models  -------------------------------------------------------------
# There are three regression models

# If we ever have bugs with the code we should make sure this web address hasn't changed
case_data <- read_csv("https://raw.githubusercontent.com/nytimes/covid-19-data/master/us-counties.csv", show_col_types = F) %>%
  filter(state == "Washington", county == "King") %>%
  mutate(
    new_cases = cases - lag(cases, 1),
    mmwr_week(date),
    week_date = mmwr_week_to_date(week = mmwr_week, year = mmwr_year)
  ) %>%
  group_by(week_date) %>%
  summarize(cases = sum(new_cases)) %>%
  ungroup() %>%
  mutate(incidence_indicator = rollmean(cases, 5, align = "right", fill = NA))

# join incidence data with other data
dat <- dat %>%
  left_join(case_data, by = "week_date")



# All Variants
mod1 <- glm(case_control_bin ~ regression_doses + week_num + incidence_indicator + alpha + delta + omicron + prior_infection + age_group + region + race_ethnicity_recode + sex, data = dat, family = "binomial")
mod1_rr <- data.frame(RR = (1 / exp(probratio(mod1, scale = "log", method = "delta")))[1:3, 1])
mod1_dat <- as.data.frame(exp(cbind(coef(mod1), confint(mod1))))[2:4, ]
names(mod1_dat) <- c("OR", "lower", "upper")
mod1_dat$doses <- c("2 Doses >6m ago", "2 Doses <6m ago", "3 Doses")
mod1_dat$variant <- "All Variants (January 2021-Present)"
mod1_dat <- mod1_dat %>% mutate(
  VE = round((1 - OR) * 100, 1),
  VE_lower = round((1 - upper) * 100, 1),
  VE_upper = round((1 - lower) * 100, 1),
  doses = factor(doses, levels = c("3 Doses", "2 Doses <6m ago", "2 Doses >6m ago"))
)
mod1_dat <- cbind(mod1_dat, mod1_rr)

# test <- dat %>% filter(encountered >= "2021-06-01", encountered <= "2022-01-31")

# Delta Specific
mod2 <- glm(delta_case ~ regression_doses + week_date + prior_infection + incidence_indicator + age_group + region + race_ethnicity_recode + sex, data = dat %>% filter(encountered >= "2021-06-20", encountered <= "2022-02-01"), family = "binomial")
mod2_rr <- data.frame(RR = (1 / exp(probratio(mod2, scale = "log", method = "delta")))[1:3, 1])
mod2_dat <- as.data.frame(exp(cbind(coef(mod2), confint(mod2))))[2:4, ]
names(mod2_dat) <- c("OR", "lower", "upper")
mod2_dat$doses <- c("2 Doses >6m ago", "2 Doses <6m ago", "3 Doses")
mod2_dat$variant <- "Delta Specific (June 2021 - Present)"
mod2_dat <- mod2_dat %>% mutate(
  VE = round((1 - OR) * 100, 1),
  VE_lower = round((1 - upper) * 100, 1),
  VE_upper = round((1 - lower) * 100, 1),
  doses = factor(doses, levels = c("3 Doses", "2 Doses <6m ago", "2 Doses >6m ago"))
)
mod2_dat <- cbind(mod2_dat, mod2_rr)


# Omicron Specific
mod3 <- glm(omicron_case ~ regression_doses + week_num + incidence_indicator + age_group + region + race_ethnicity_recode + sex, data = dat %>% filter(encountered >= "2021-12-12", prior_infection == 0), family = "binomial")
mod3_rr <- data.frame(RR = (1 / exp(probratio(mod3, scale = "log", method = "delta")))[1:3, 1])
mod3_dat <- as.data.frame(exp(cbind(coef(mod3), confint(mod3))))[2:4, ]
names(mod3_dat) <- c("OR", "lower", "upper")
mod3_dat$doses <- c("2 Doses >6m ago", "2 Doses <6m ago", "3 Doses")
mod3_dat$variant <- "Omicron Specific (December 2021 - Present)"
mod3_dat <- mod3_dat %>% mutate(
  VE = round((1 - OR) * 100, 1),
  VE_lower = round((1 - upper) * 100, 1),
  VE_upper = round((1 - lower) * 100, 1),
  doses = factor(doses, levels = c("3 Doses", "2 Doses <6m ago", "2 Doses >6m ago"))
)
mod3_dat <- cbind(mod3_dat, mod3_rr)


# combine datasets
# select variables
# cut off lower CIs if <0
VE_dat <- rbind(mod1_dat, mod2_dat, mod3_dat) %>%
  mutate(range = VE_upper - VE_lower) %>%
  filter(range < 80) %>%
  select(doses, variant, VE_lower, VE, VE_upper, RR) %>%
  mutate(VE_lower = ifelse(VE_lower < 0, 0, VE_lower))


write.csv(VE_dat, "data/ve_variant.csv", row.names = F)
# This dataframe is used to make the VE whisker plots in Tableau